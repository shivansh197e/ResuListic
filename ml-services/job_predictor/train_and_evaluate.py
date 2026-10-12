"""
train_and_evaluate.py — ML benchmarking, training, and evaluation suite.
Benchmarks Logistic Regression, Random Forest, HistGradientBoosting, and LinearSVC.
Evaluates Precision, Recall, F1-scores, Confusion Matrix, and Multi-Class ROC Curves.
Saves the top-performing model pipeline and diagnostic plots.
"""
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Headless backend for image generation
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder, label_binarize
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    auc,
    precision_recall_curve,
    confusion_matrix,
    ConfusionMatrixDisplay,
    classification_report,
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV

# Resilient path resolution
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_SERVICES_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _ML_SERVICES_DIR not in sys.path:
    sys.path.insert(0, _ML_SERVICES_DIR)

from job_predictor.data_generator import load_or_generate_dataset, TARGET_DOMAINS

ARTIFACTS_DIR = os.path.join(_CURRENT_DIR, "model_artifacts")
PLOTS_DIR = os.path.join(_CURRENT_DIR, "evaluation_plots")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)


def build_preprocessor() -> ColumnTransformer:
    """Builds early-fusion ColumnTransformer for text and numerical features."""
    return ColumnTransformer(
        transformers=[
            (
                "text_tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=1500,
                    sublinear_tf=True,
                    token_pattern=r"(?u)\b\w[\w-]+\b",
                ),
                "resume_text",
            ),
            (
                "num_scaler",
                StandardScaler(),
                ["mcq_score", "coding_score", "total_score", "num_skills"],
            ),
        ],
        remainder="drop",
    )


def train_and_benchmark_models(df: pd.DataFrame) -> dict:
    """
    Splits data before fitting, benchmarks 4 candidate classifiers,
    computes cross-validation and test metrics, exports plots,
    and serializes the winning pipeline.
    """
    print("\n" + "=" * 65)
    print(" RESULISTIC JOB PREDICTOR: MODEL BENCHMARKING & EVALUATION")
    print("=" * 65)

    X = df[["resume_text", "mcq_score", "coding_score", "total_score", "num_skills"]]
    y_raw = df["domain"]

    # 1. Encode labels
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(y_raw)
    class_names = list(label_encoder.classes_)
    n_classes = len(class_names)

    # 2. Strict Featurization Ordering: Split BEFORE any preprocessing
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Dataset split: Train={len(X_train)} samples, Test={len(X_test)} samples")
    print(f"Target classes ({n_classes}): {class_names}")

    # Binarize test labels for Multi-Class ROC analysis (One-vs-Rest)
    y_test_bin = label_binarize(y_test, classes=list(range(n_classes)))

    # 3. Candidate models to benchmark
    candidate_classifiers = {
        "Logistic Regression": LogisticRegression(
            max_iter=1000,
            C=1.5,
            random_state=42,
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=120,
            max_depth=20,
            random_state=42,
            n_jobs=-1,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=100,
            random_state=42,
        ),
        "Calibrated LinearSVC": CalibratedClassifierCV(
            estimator=LinearSVC(random_state=42, max_iter=2000),
            cv=3,
        ),
    }

    results = {}
    fitted_pipelines = {}
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # 4. Benchmarking Loop
    print("\n[Benchmarking Models with 5-Fold Stratified Cross-Validation]")
    print("-" * 65)

    for name, clf in candidate_classifiers.items():
        # Build pipeline
        preprocessor = build_preprocessor()

        # HistGradientBoosting requires dense matrices
        if name == "HistGradientBoosting":
            from sklearn.base import TransformerMixin, BaseEstimator
            class DenseTransformer(BaseEstimator, TransformerMixin):
                def fit(self, X, y=None): return self
                def transform(self, X):
                    return X.toarray() if hasattr(X, "toarray") else X

            pipe = Pipeline([
                ("preprocessor", preprocessor),
                ("to_dense", DenseTransformer()),
                ("classifier", clf),
            ])
        else:
            pipe = Pipeline([
                ("preprocessor", preprocessor),
                ("classifier", clf),
            ])

        # 5-Fold Cross Validation on Training Data
        cv_scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="f1_macro", n_jobs=-1)
        mean_cv_f1 = float(np.mean(cv_scores))
        std_cv_f1 = float(np.std(cv_scores))

        # Train on entire training set
        pipe.fit(X_train, y_train)
        fitted_pipelines[name] = pipe

        # Predict on Test set
        y_pred = pipe.predict(X_test)
        if hasattr(pipe, "predict_proba"):
            y_proba = pipe.predict_proba(X_test)
        elif hasattr(pipe.named_steps["classifier"], "predict_proba"):
            y_proba = pipe.named_steps["classifier"].predict_proba(pipe.named_steps["preprocessor"].transform(X_test))
        else:
            y_proba = None

        acc = accuracy_score(y_test, y_pred)
        prec_macro = precision_score(y_test, y_pred, average="macro", zero_division=0)
        rec_macro = recall_score(y_test, y_pred, average="macro", zero_division=0)
        f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)
        f1_weighted = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        # Multi-class ROC-AUC (One-vs-Rest)
        if y_proba is not None:
            roc_auc_ovr = roc_auc_score(y_test_bin, y_proba, multi_class="ovr", average="macro")
        else:
            roc_auc_ovr = 0.0

        results[name] = {
            "cv_f1_macro_mean": round(mean_cv_f1, 4),
            "cv_f1_macro_std": round(std_cv_f1, 4),
            "test_accuracy": round(acc, 4),
            "test_precision_macro": round(prec_macro, 4),
            "test_recall_macro": round(rec_macro, 4),
            "test_f1_macro": round(f1_macro, 4),
            "test_f1_weighted": round(f1_weighted, 4),
            "test_roc_auc_macro": round(roc_auc_ovr, 4),
            "y_pred": y_pred,
            "y_proba": y_proba,
        }

        print(
            f"{name:<22} | CV F1: {mean_cv_f1:.3f} (±{std_cv_f1:.3f}) | "
            f"Test Acc: {acc:.3f} | Prec: {prec_macro:.3f} | Rec: {rec_macro:.3f} | "
            f"F1: {f1_macro:.3f} | ROC-AUC: {roc_auc_ovr:.3f}"
        )

    # 5. Select Winning Model based on test Macro F1 & ROC-AUC
    best_model_name = max(
        results.keys(),
        key=lambda k: (results[k]["test_f1_macro"], results[k]["test_roc_auc_macro"])
    )
    best_pipe = fitted_pipelines[best_model_name]
    best_metrics = results[best_model_name]
    print("\n" + "=" * 65)
    print(f" WINNING MODEL SELECTED: {best_model_name}")
    print(f" Test Macro F1: {best_metrics['test_f1_macro']:.4f} | ROC-AUC: {best_metrics['test_roc_auc_macro']:.4f}")
    print("=" * 65)

    # 6. Detailed Classification Report for Best Model
    print("\n[Detailed Classification Report for Winning Model]")
    print(classification_report(y_test, best_metrics["y_pred"], target_names=class_names, digits=4))

    # 7. Generate Diagnostic Plots for Best Model
    _generate_evaluation_plots(
        y_test=y_test,
        y_test_bin=y_test_bin,
        y_pred=best_metrics["y_pred"],
        y_proba=best_metrics["y_proba"],
        class_names=class_names,
        model_name=best_model_name,
        output_dir=PLOTS_DIR,
    )

    # 8. Save Model Pipeline & Label Encoder
    model_save_path = os.path.join(ARTIFACTS_DIR, "job_classifier.joblib")
    encoder_save_path = os.path.join(ARTIFACTS_DIR, "label_encoder.joblib")
    metrics_save_path = os.path.join(ARTIFACTS_DIR, "benchmark_metrics.json")

    joblib.dump(best_pipe, model_save_path)
    joblib.dump(label_encoder, encoder_save_path)

    serializable_metrics = {
        name: {k: v for k, v in m.items() if k not in ("y_pred", "y_proba")}
        for name, m in results.items()
    }
    serializable_metrics["best_model"] = best_model_name
    serializable_metrics["classes"] = class_names

    with open(metrics_save_path, "w", encoding="utf-8") as f:
        json.dump(serializable_metrics, f, indent=2)

    print(f"\nModel pipeline saved to: {model_save_path}")
    print(f"Label encoder saved to:   {encoder_save_path}")
    print(f"Benchmark summary saved to: {metrics_save_path}")

    return {
        "best_model_name": best_model_name,
        "results": serializable_metrics,
        "class_names": class_names,
    }


def _generate_evaluation_plots(
    y_test: np.ndarray,
    y_test_bin: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    class_names: list,
    model_name: str,
    output_dir: str,
):
    """Generates ROC curves, PR curves, and Confusion Matrix plots."""
    n_classes = len(class_names)
    colors = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"]

    # ── 1. Multi-Class ROC Curves (One-vs-Rest) ──────────────────────────────
    plt.figure(figsize=(9, 7))
    fpr = dict()
    tpr = dict()
    roc_auc = dict()

    for i in range(n_classes):
        fpr[i], tpr[i], _ = roc_curve(y_test_bin[:, i], y_proba[:, i])
        roc_auc[i] = auc(fpr[i], tpr[i])
        plt.plot(
            fpr[i],
            tpr[i],
            color=colors[i % len(colors)],
            lw=2,
            label=f"{class_names[i]} (AUC = {roc_auc[i]:.3f})",
        )

    # Compute micro-average ROC curve
    fpr["micro"], tpr["micro"], _ = roc_curve(y_test_bin.ravel(), y_proba.ravel())
    roc_auc["micro"] = auc(fpr["micro"], tpr["micro"])
    plt.plot(
        fpr["micro"],
        tpr["micro"],
        label=f"Micro-average (AUC = {roc_auc['micro']:.3f})",
        color="deeppink",
        linestyle=":",
        linewidth=3,
    )

    # Diagonal reference line
    plt.plot([0, 1], [0, 1], "k--", lw=1.5, alpha=0.7)
    plt.xlim([-0.02, 1.02])
    plt.ylim([-0.02, 1.05])
    plt.xlabel("False Positive Rate (1 - Specificity)", fontsize=11, fontweight="bold")
    plt.ylabel("True Positive Rate (Sensitivity / Recall)", fontsize=11, fontweight="bold")
    plt.title(f"Multi-Class ROC Curves (OvR) — {model_name}", fontsize=13, fontweight="bold")
    plt.legend(loc="lower right", fontsize=9, framealpha=0.9)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    roc_path = os.path.join(output_dir, "roc_curves.png")
    plt.savefig(roc_path, dpi=200)
    plt.close()
    print(f"[Plot Export] Multi-class ROC curves saved to: {roc_path}")

    # ── 2. Precision-Recall Curves ───────────────────────────────────────────
    plt.figure(figsize=(9, 7))
    for i in range(n_classes):
        precision, recall, _ = precision_recall_curve(y_test_bin[:, i], y_proba[:, i])
        pr_auc = auc(recall, precision)
        plt.plot(
            recall,
            precision,
            color=colors[i % len(colors)],
            lw=2,
            label=f"{class_names[i]} (PR-AUC = {pr_auc:.3f})",
        )

    plt.xlabel("Recall", fontsize=11, fontweight="bold")
    plt.ylabel("Precision", fontsize=11, fontweight="bold")
    plt.title(f"Precision-Recall Curves — {model_name}", fontsize=13, fontweight="bold")
    plt.legend(loc="lower left", fontsize=9, framealpha=0.9)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    pr_path = os.path.join(output_dir, "precision_recall_curves.png")
    plt.savefig(pr_path, dpi=200)
    plt.close()
    print(f"[Plot Export] Precision-Recall curves saved to: {pr_path}")

    # ── 3. Confusion Matrix ──────────────────────────────────────────────────
    cm = confusion_matrix(y_test, y_pred, normalize="true")
    fig, ax = plt.subplots(figsize=(8, 7))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
    disp.plot(cmap="Blues", ax=ax, values_format=".2f", colorbar=True)
    plt.title(f"Normalized Confusion Matrix — {model_name}", fontsize=12, fontweight="bold")
    plt.xticks(rotation=30, ha="right", fontsize=9)
    plt.yticks(fontsize=9)
    plt.tight_layout()
    cm_path = os.path.join(output_dir, "confusion_matrix.png")
    plt.savefig(cm_path, dpi=200)
    plt.close()
    print(f"[Plot Export] Confusion Matrix saved to: {cm_path}")


if __name__ == "__main__":
    dataset = load_or_generate_dataset()
    train_and_benchmark_models(dataset)
