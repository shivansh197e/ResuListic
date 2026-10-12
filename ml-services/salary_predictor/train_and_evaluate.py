"""
train_and_evaluate.py — Trains and benchmarks Scikit-Learn regression models for salary prediction (4 LPA to 30+ LPA).
Saves the best-performing model pipeline and compensation diagnostic artifacts.
"""
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_SERVICES_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, _ML_SERVICES_DIR)

from salary_predictor.data_generator import generate_salary_dataset

ARTIFACTS_DIR = os.path.join(_CURRENT_DIR, "model_artifacts")
PLOTS_DIR = os.path.join(_CURRENT_DIR, "evaluation_plots")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)


def build_preprocessor() -> ColumnTransformer:
    """Constructs column transformer for categorical domains and numerical score metrics."""
    return ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["domain", "experience_tier"],
            ),
            (
                "num",
                StandardScaler(),
                ["num_skills", "high_impact_skills", "mcq_score", "coding_score", "total_score"],
            ),
        ],
        remainder="drop",
    )


def train_and_benchmark_salary_models(df: pd.DataFrame) -> dict:
    """Trains candidate regressors and serializes the winning model pipeline."""
    print("\n" + "=" * 65)
    print(" RESULISTIC SALARY PREDICTOR: BENCHMARKING (4 LPA - 30+ LPA)")
    print("=" * 65)

    feature_cols = ["domain", "experience_tier", "num_skills", "high_impact_skills", "mcq_score", "coding_score", "total_score"]
    X = df[feature_cols]
    y = df["salary_lpa"]

    # Strict split before fitting
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)
    print(f"Dataset split: Train={len(X_train)} samples, Test={len(X_test)} samples")
    print(f"Target range: {y.min():.1f} LPA to {y.max():.1f} LPA (Mean: {y.mean():.1f} LPA)")

    candidate_regressors = {
        "Gradient Boosting Regressor": GradientBoostingRegressor(
            n_estimators=120,
            learning_rate=0.08,
            max_depth=4,
            random_state=42,
        ),
        "Random Forest Regressor": RandomForestRegressor(
            n_estimators=100,
            max_depth=12,
            random_state=42,
            n_jobs=-1,
        ),
        "Ridge Regressor": Ridge(alpha=1.0),
    }

    results = {}
    fitted_pipelines = {}
    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    for name, reg in candidate_regressors.items():
        pipe = Pipeline([
            ("preprocessor", build_preprocessor()),
            ("regressor", reg),
        ])

        cv_r2 = cross_val_score(pipe, X_train, y_train, cv=kf, scoring="r2", n_jobs=-1)
        mean_cv_r2 = float(np.mean(cv_r2))

        pipe.fit(X_train, y_train)
        fitted_pipelines[name] = pipe

        y_pred = pipe.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))

        results[name] = {
            "cv_r2_mean": round(mean_cv_r2, 4),
            "test_r2": round(r2, 4),
            "test_mae_lpa": round(mae, 4),
            "test_rmse_lpa": round(rmse, 4),
            "y_pred": y_pred,
        }

        print(
            f"{name:<28} | CV R2: {mean_cv_r2:.3f} | "
            f"Test R2: {r2:.3f} | MAE: {mae:.2f} LPA | RMSE: {rmse:.2f} LPA"
        )

    # Pick best model based on test R2 and MAE
    best_model_name = max(results.keys(), key=lambda k: results[k]["test_r2"])
    best_pipe = fitted_pipelines[best_model_name]
    best_metrics = results[best_model_name]

    print("\n" + "=" * 65)
    print(f" WINNING MODEL: {best_model_name}")
    print(f" Test R2: {best_metrics['test_r2']} | MAE: {best_metrics['test_mae_lpa']} LPA")
    print("=" * 65)

    # Save visualization
    _generate_regression_plot(y_test, best_metrics["y_pred"], best_model_name, PLOTS_DIR)

    # Save artifacts
    model_save_path = os.path.join(ARTIFACTS_DIR, "salary_model.joblib")
    metrics_save_path = os.path.join(ARTIFACTS_DIR, "salary_metrics.json")
    joblib.dump(best_pipe, model_save_path)

    serializable = {
        name: {k: v for k, v in m.items() if k != "y_pred"}
        for name, m in results.items()
    }
    serializable["best_model"] = best_model_name
    with open(metrics_save_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

    print(f"[Model Saved] {model_save_path}")
    return results


def _generate_regression_plot(y_test, y_pred, model_name: str, output_dir: str):
    """Generates Actual vs Predicted Salary plot."""
    plt.figure(figsize=(8, 7))
    plt.scatter(y_test, y_pred, alpha=0.5, color="#2563eb", edgecolors="none", s=25)
    
    # 45-degree ideal fit line
    lims = [min(y_test.min(), y_pred.min()) - 1, max(y_test.max(), y_pred.max()) + 1]
    plt.plot(lims, lims, "r--", lw=2, label="Perfect Prediction (y = x)")
    
    plt.xlim(lims)
    plt.ylim(lims)
    plt.xlabel("Actual Salary (LPA)", fontsize=11, fontweight="bold")
    plt.ylabel("Predicted Salary (LPA)", fontsize=11, fontweight="bold")
    plt.title(f"Salary Prediction: Actual vs. Predicted — {model_name}", fontsize=12, fontweight="bold")
    plt.legend(loc="upper left")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    
    plot_path = os.path.join(output_dir, "predicted_vs_actual_salary.png")
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"[Plot Export] {plot_path}")


if __name__ == "__main__":
    data_csv = os.path.join(_ML_SERVICES_DIR, "..", "datasets", "salary_training_data.csv")
    df = generate_salary_dataset(n_samples=3000, output_csv=data_csv)
    train_and_benchmark_salary_models(df)
