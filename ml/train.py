"""
Обучение модели предсказания цены недвижимости.
Таргет: log1p(price_per_m2) → предсказание умножается на total_area.
Запуск: python ml/train.py
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from catboost import CatBoostRegressor, Pool
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

# --- Пути ---
DATA_PATH     = Path("data/listings.parquet")
ARTIFACTS_DIR = Path("ml/artifacts")
MODEL_PATH    = ARTIFACTS_DIR / "model.cbm"
METRICS_PATH  = ARTIFACTS_DIR / "metrics.json"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Фичи ---
NUM_FEATURES = [
    "total_area", "floor", "floors", "distance",
    "lat", "lon", "floor_ratio",
    "month", "quarter",
]
CAT_FEATURES = [
    "rooms_code", "remont_code", "hometype_code", "deal_type_code",
    "category", "property_kind", "region_id", "bucket", "okrug",
]
BIN_FEATURES = [
    "new_building", "is_first_floor", "is_top_floor",
]
ALL_FEATURES = NUM_FEATURES + CAT_FEATURES + BIN_FEATURES
TARGET_PM2   = "price_per_m2"
TARGET_PRICE = "price"


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["floor_ratio"]    = df["floor"] / df["floors"]
    df["is_first_floor"] = (df["floor"] == 1).astype("Int8")
    df["is_top_floor"]   = (df["floor"] == df["floors"]).astype("Int8")
    return df


def prepare_cat_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in CAT_FEATURES + BIN_FEATURES:
        na_mask = df[col].isna()
        df[col] = df[col].astype(str)
        df.loc[na_mask, col] = ""
    return df


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true > 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def baseline_median_by_region(
    X_train: pd.DataFrame, y_train: pd.Series,
    X_test:  pd.DataFrame, y_test:  pd.Series,
) -> dict:
    """Naive baseline: медиана price_per_m2 по region_id."""
    medians = y_train.groupby(X_train["region_id"]).median()
    global_median = y_train.median()
    y_pred = X_test["region_id"].map(medians).fillna(global_median)
    return {
        "mae":  mean_absolute_error(y_test, y_pred),
        "rmse": root_mean_squared_error(y_test, y_pred),
        "mape": mape(y_test.values, y_pred.values),
    }


def main():
    # --- Загрузка данных ---
    print("Загрузка данных...")
    df = pd.read_parquet(DATA_PATH)
    print(f"  Строк: {len(df):,}")

    # --- Feature engineering ---
    df = feature_engineering(df)
    df = prepare_cat_features(df)

    # --- Отбор фич и таргета ---
    X      = df[ALL_FEATURES]
    y_pm2  = df[TARGET_PM2]          # цена за м² (таргет модели)
    y_price = df[TARGET_PRICE]       # абсолютная цена (для итоговых метрик)
    area    = df["total_area"]

    y_pm2_log = np.log1p(y_pm2)

    # --- Train / Test split ---
    X_train, X_test, y_log_train, y_log_test, price_train, price_test, area_test = (
        *train_test_split(X, y_pm2_log, y_price, test_size=0.2, random_state=42),
        area.loc[y_pm2_log.index].iloc[
            int(len(y_pm2_log) * 0.8):
        ],
    )
    # Правильный split area вместе с X
    (X_train, X_test,
     y_log_train, y_log_test,
     price_train, price_test) = train_test_split(
        X, y_pm2_log, y_price, test_size=0.2, random_state=42
    )
    area_test = df.loc[X_test.index, "total_area"]

    print(f"  Train: {len(X_train):,}  |  Test: {len(X_test):,}")

    # --- Baseline по price_per_m2 ---
    y_pm2_train = np.expm1(y_log_train)
    y_pm2_test  = np.expm1(y_log_test)

    print("\nBaseline (медиана pm2 по региону):")
    baseline = baseline_median_by_region(X_train, y_pm2_train, X_test, y_pm2_test)
    baseline_price_pred = baseline_median_by_region(
        X_train, y_pm2_train, X_test, y_pm2_test
    )
    print(f"  MAE  (pm2): {baseline['mae']:>12,.0f} руб/м²")
    print(f"  MAPE (pm2): {baseline['mape']:>11.1f} %")

    # --- CatBoost Pool ---
    cat_idx = [ALL_FEATURES.index(c) for c in CAT_FEATURES + BIN_FEATURES]
    train_pool = Pool(X_train, y_log_train, cat_features=cat_idx)
    test_pool  = Pool(X_test,  y_log_test,  cat_features=cat_idx)

    # --- Обучение ---
    print("\nОбучение CatBoost...")
    model = CatBoostRegressor(
        iterations=2000,
        learning_rate=0.05,
        depth=6,
        l2_leaf_reg=5,
        loss_function="RMSE",
        eval_metric="RMSE",
        early_stopping_rounds=100,
        random_seed=42,
        verbose=200,
    )
    model.fit(train_pool, eval_set=test_pool)

    # --- Метрики на тесте ---
    y_pm2_pred = np.expm1(model.predict(X_test))
    y_price_pred = y_pm2_pred * area_test.values

    # Метрики по цене за м²
    mae_pm2  = mean_absolute_error(y_pm2_test, y_pm2_pred)
    mape_pm2 = mape(y_pm2_test.values, y_pm2_pred)

    # Метрики по абсолютной цене
    mae_price  = mean_absolute_error(price_test, y_price_pred)
    rmse_price = root_mean_squared_error(price_test, y_price_pred)
    mape_price = mape(price_test.values, y_price_pred)

    print("\nРезультаты модели (цена за м²):")
    print(f"  MAE:  {mae_pm2:>12,.0f} руб/м²")
    print(f"  MAPE: {mape_pm2:>11.1f} %")

    print("\nРезультаты модели (итоговая цена):")
    print(f"  MAE:  {mae_price:>15,.0f} руб.")
    print(f"  RMSE: {rmse_price:>15,.0f} руб.")
    print(f"  MAPE: {mape_price:>14.1f} %")

    print("\nУлучшение vs baseline (MAPE pm2):")
    print(f"  -{(1 - mape_pm2 / baseline['mape']) * 100:.1f}%")

    # --- Feature importance ---
    print("\nТоп-10 важных фич:")
    importances = pd.Series(
        model.get_feature_importance(), index=ALL_FEATURES
    ).sort_values(ascending=False)
    for feat, imp in importances.head(10).items():
        print(f"  {feat:<20} {imp:.2f}")

    # --- Сохранение ---
    model.save_model(str(MODEL_PATH))
    print(f"\nМодель сохранена: {MODEL_PATH}")

    metrics = {
        "model_pm2":   {"mae": mae_pm2,   "mape": mape_pm2},
        "model_price": {"mae": mae_price, "rmse": rmse_price, "mape": mape_price},
        "baseline":    baseline,
        "best_iteration": model.best_iteration_,
        "features": ALL_FEATURES,
        "cat_features": CAT_FEATURES + BIN_FEATURES,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"Метрики сохранены: {METRICS_PATH}")


if __name__ == "__main__":
    main()
