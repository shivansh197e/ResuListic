# RESULISTIC: AI MINI PROJECT PRESENTATION DECK (PPT)
### Slide-by-Slide Deck Content, Visual Layouts, and Presenter Scripts

---

## SLIDE 1: TITLE SLIDE
* **Slide Title:** RESULISTIC
* **Subtitle:** An Intelligent Multimodal Resume Parsing, Dynamic Competency Assessment, and Career Domain / Salary Prediction Platform
* **Course:** Artificial Intelligence Mini Project (B.Tech / B.E. Computer Science & Engineering)
* **Academic Year:** 2025 – 2026
* **Team Details:**
  * **[Student 1 Name - e.g., Vedant Khare]** ([Roll Number 1])
  * **[Student 2 Name - e.g., Shivansh]** ([Roll Number 2])
  * **[Student 3 Name / Optional]** ([Roll Number 3])
* **Under the Guidance of:** [Project Guide / Mentor Name], [Designation, Department]
* **Institution:** [College / University / Department Name]

> **🗣️ Presenter Script (30 Seconds):**  
> *"Good morning respected evaluators and professors. Today our team is presenting our AI Mini Project titled 'ResuListic'—an end-to-end career intelligence and assessment platform that solves one of the most critical challenges in the tech hiring ecosystem: the disconnect between what candidates claim on static resumes and their actual, hands-on programming and problem-solving competence."*

---

## SLIDE 2: INTRODUCTION, PROBLEM & MOTIVATION
* **The Problem:**
  * **Resume Inflation & Keyword Stuffing:** Candidates pack resumes with buzzwords to trick traditional ATS (Applicant Tracking Systems) without possessing real proficiency.
  * **Superficial ATS Filters:** Existing screening tools rely on rigid keyword matching, rejecting talented candidates who use non-standard phrasing.
  * **No Real-Time Validation:** Resumes represent unverified historical claims. Recruiters spend hours interviewing candidates who cannot solve basic coding challenges.
  * **Subjective Compensation:** Salary offers often lack empirical calibration, leading to wage disparities and mismatched expectations.
* **Simple Real-World Example:**
  * *Candidate A* puts `"Docker, Kubernetes, Microservices"` on their resume after watching a 1-hour tutorial. An ATS shortlists them. When asked to write a simple container config or debug an API in an interview, they fail—wasting 3 weeks of recruiter time.
* **Why AI is Essential:**
  * Combines **Computer Vision (OCR)** for heterogeneous documents, **NLP** for semantic skill taxonomy normalization, **LLM-as-a-Judge** for automated code evaluation, and **Supervised ML** for data-driven domain and salary prediction.

> **🗣️ Presenter Script (60 Seconds):**  
> *"Every year, millions of resumes are screened using legacy Applicant Tracking Systems that rely purely on basic keyword matching. This creates two huge problems: qualified candidates get filtered out simply because they didn't use specific buzzwords, while other candidates game the system by stuffing keywords into their resumes. A candidate might claim experience in React and Docker, but when given a simple coding test, they fail. ResuListic replaces this broken, static system with an end-to-end AI pipeline that parses the resume, immediately challenges the candidate with an adaptive 90-minute technical exam, uses an AI Judge to grade their code and Big-O complexity, and then accurately predicts their true career domain and market salary package."*

---

## SLIDE 3: PROJECT OBJECTIVES
* **1. Multimodal Resume Ingestion:** Extract text seamlessly from PDF, DOCX, and images (PNG/JPG) using an automatic OCR fallback engine.
* **2. NLP Skill & Entity Normalization:** Extract candidate contact details and map technical skills into *High* and *Medium* confidence tiers against a standardized 170+ technology taxonomy.
* **3. 90-Minute Adaptive Assessment Engine:** Orchestrate a non-repetitive 10-question timed exam (5 generative MCQs, 3 moderate coding questions, and 2 advanced coding challenges via a circular linked list pointer).
* **4. Automated LLM-as-a-Judge Code Evaluation:** Grade candidate Python solutions in real-time for functional correctness, score (0–100), Big-O time complexity, and code quality.
* **5. Multi-Class Job Domain Classification:** Predict primary career domain across 5 specializations and recommend career transition pathways with missing skill gaps.
* **6. Continuous Salary Compensation Modeling:** Predict market CTC packages (4.0 to 30.0+ LPA) based on empirical skill equity and test performance.
* **7. Production-Ready Full-Stack Web App:** Deliver a reactive React 18 single-page application served via FastAPI and containerized using Docker.

> **🗣️ Presenter Script (45 Seconds):**  
> *"Our project had seven core objectives. First, support any resume format—even scanned phone photos—via automated OCR. Second, extract and normalize 170+ skills into high and medium confidence tiers using spaCy. Third, generate an adaptive, 90-minute timed assessment. Fourth, use an LLM-as-a-Judge on Groq to evaluate candidate code and Big-O complexity. Fifth and sixth, train machine learning models to classify their career domain and predict their market salary between 4 and 30 LPA. And finally, deploy everything in a live, containerized web application."*

---

## SLIDE 4: EXISTING WORK & LITERATURE REVIEW
* **Key Academic Foundations:**
  1. **Roy et al. (2020) — NER Resume Parsing:** Used Bi-LSTM-CRF for entity extraction. *Limitation:* Brittle on multi-column layouts; no OCR for scanned images; no competence testing.
  2. **Tosun & Gültekin (2022) — Semantic Skill Extraction:** Ontology-based skill matching. *Limitation:* Purely descriptive; cannot verify whether candidate can actually program.
  3. **Zheng et al. (2023) — LLM-as-a-Judge:** Pioneered using large models to evaluate reasoning and code. *Our Innovation:* Adapted this specifically for real-time technical interviews with structured Big-O complexity extraction and deterministic fallbacks.
  4. **Gaur & Bansal (2023) — Tech Salary Prediction:** Used Gradient Boosting on self-reported survey data. *Our Innovation:* We combine self-reported skills with empirical, AI-graded test scores for high-accuracy compensation modeling.
* **The Research Gap:**
  * Existing solutions treat parsing, testing, and job prediction in separate silos. **ResuListic unifies all four stages into an automated, closed-loop pipeline.**

> **🗣️ Presenter Script (45 Seconds):**  
> *"When reviewing existing literature, we found that past systems work in disconnected silos. Roy and Tosun focused strictly on parsing static text without testing the candidate. Zheng et al. showed that LLMs make excellent judges, but applied it to general chat rather than technical hiring. And recent salary prediction research relied only on self-reported survey data. ResuListic bridges these gaps by directly linking what's extracted from the resume to a real coding exam, feeding those scores into an early-fusion machine learning model for domain and salary prediction."*

---

## SLIDE 5: PROPOSED SYSTEM ARCHITECTURE
* **Visual Diagram:** System Workflow Flowchart (Ingestion $\rightarrow$ NLP $\rightarrow$ Exam Engine $\rightarrow$ LLM Judge $\rightarrow$ ML Predictors $\rightarrow$ Dashboard)
* **Modular Pipeline Components:**
  * **1. Ingestion Layer:** `pdfplumber` / `python-docx` $\rightarrow$ Fallback to `pdf2image` + `pytesseract`.
  * **2. NLP Layer:** spaCy `en_core_web_md` + Regex Entity Matcher + Taxonomy Engine.
  * **3. Assessment Engine:** Gemini / Groq API (5 MCQs) + MongoDB Circular Modulo Selector (`(ptr+2)%50` for 2 Hard Problems) + 90-Minute HUD Countdown.
  * **4. Evaluation Engine:** Groq Cloud (`llama-3.3-70b-versatile` / `qwen3.8-27b`) returning `{passed, score, feedback, time_complexity}`.
  * **5. ML Intelligence Layer:** ColumnTransformer (TF-IDF + Scaled Metrics) $\rightarrow$ Logistic Regression (Domain) + Gradient Boosting (Salary).
  * **6. Presentation Layer:** FastAPI Backend + React 18 / Tailwind CSS SPA + Docker Container.

> **🗣️ Presenter Script (60 Seconds):**  
> *"Here is our complete system architecture. It begins at the Ingestion Layer, where any resume—PDF, Word, or image—is parsed. If a candidate uploads a scanned photo, our system automatically falls back to Poppler and Tesseract OCR. Next, our NLP layer classifies sections and maps extracted terms to 170+ standardized skills. This populates a customized 10-question test session: 5 easy MCQs generated on the fly, 3 moderate problems, and 2 hard algorithmic challenges chosen by our circular modulo algorithm so retakes are never identical. When the candidate writes code in our in-browser editor, an LLM Judge evaluates their solution in under two seconds. Finally, our early-fusion ML models output their career domain and market salary package."*

---

## SLIDE 6: DATASET & MULTIMODAL INPUTS
* **Resume Ingestion Dataset:**
  * Evaluated across 50+ diverse technical resumes: single-column, double-column, LaTeX layouts, DOCX files, and mobile phone photo captures.
* **Assessment Question Bank:**
  * 50+ Curated Data Structures & Algorithms challenges (Array, String, Trees, Dynamic Programming, Graphs) stored in MongoDB Atlas collections (`questions_moderate`, `questions_hard`, `solutions`).
* **ML Training & Benchmark Dataset:**
  * **Size:** 1,000 synthetic, highly curated candidate profiles spanning 5 technical domains:
    * *Backend Web Development* (Python, Node.js, Django, PostgreSQL, Redis)
    * *Cloud & DevOps* (Docker, Kubernetes, AWS, Terraform, CI/CD)
    * *Data Science & AI/ML* (PyTorch, TensorFlow, Pandas, Scikit-Learn, Computer Vision)
    * *Frontend Web Development* (React, TypeScript, Next.js, Tailwind, Vue)
    * *Mobile App Development* (Flutter, React Native, Kotlin, Swift, iOS)
  * **Feature Attributes:** Resume body text, extracted skill tokens, MCQ test score (0–100), Coding test score (0–100), Total score, and Skill count.
  * **Target Outputs:** Domain class (Categorical, 5 classes) & Salary Package (Continuous, 4.0 to 30.0+ LPA).

> **🗣️ Presenter Script (45 Seconds):**  
> *"To train and benchmark our machine learning models, we developed a comprehensive dataset of 1,000 candidate profiles across five core software domains: Backend, Cloud/DevOps, Data Science/AI, Frontend, and Mobile Development. Each record contains the full resume text, skill counts, and authentic assessment performance metrics like MCQ and coding scores. In addition, our MongoDB database houses over 50 vetted algorithmic coding problems with hidden reference solutions, and our parser was verified across dozens of challenging resume layouts."*

---

## SLIDE 7: METHODOLOGY & AI/ML TECHNIQUES
* **1. Information Extraction & Skill Stratification:**
  * spaCy linguistic model (`en_core_web_md`) extracts entities.
  * **Confidence Formula:** Skills appearing in both the Skills section and Experience/Projects sections are tagged **High Confidence**; isolated mentions receive **Medium Confidence**.
* **2. The Circular Linked List Modulo Algorithm:**
  * Ensures non-repeating Hard coding questions across test attempts:
    $$\text{new\_pointer} = (\text{old\_pointer} + 2) \pmod{50}$$
* **3. LLM-as-a-Judge Code Evaluation:**
  * Groq-hosted LLaMA-3.3-70B analyzes student code against hidden reference solutions.
  * Enforces strict JSON contracts with functional correctness, 0–100 score, stylistic feedback, and Big-O computational complexity.
* **4. Early-Fusion Feature Representation:**
  * Text features: TF-IDF vectorization with sublinear term frequency ($1,500$ max features, unigrams + bigrams).
  * Numerical features: `StandardScaler` applied to MCQ score, coding score, total score, and skill count.
  * Combined via `ColumnTransformer` before model fitting.

> **🗣️ Presenter Script (60 Seconds):**  
> *"Let's look at the core AI methodology. First, we use a two-tier confidence stratification in spaCy: a skill is marked 'High Confidence' only if it appears in both the skills list and a project description, eliminating casual buzzwords. Second, we solved the problem of repetitive tests using a circular modulo pointer in MongoDB that advances by two on every attempt across 50 vetted problems. Third, our LLM Judge uses Groq's high-speed inference to analyze submitted code against hidden test cases, returning not just pass/fail, but exact Big-O time complexity. Finally, we use early-fusion feature engineering, combining 1,500 TF-IDF n-gram text features with standardized test scores."*

---

## SLIDE 8: MACHINE LEARNING MODELS & ARCHITECTURE
* **Multi-Class Job Classifier Models Benchmarked:**
  1. **Multinomial Logistic Regression (Selected Production Model):** Minimizes multinomial cross-entropy with $L_2$ regularization. Delivers calibrated softmax probabilities for career switch pathways.
  2. **Random Forest Classifier:** 200 de-correlated trees with bootstrap aggregation.
  3. **HistGradientBoostingClassifier:** Binned gradient boosting for non-linear decision surfaces.
  4. **Calibrated LinearSVC:** Support vector machine with Platt scaling.
* **Continuous Salary Regressor Models Benchmarked:**
  1. **Gradient Boosting Regressor (Selected Production Model):** Sequential boosting of shallow regression trees minimizing Huber loss.
  2. **Random Forest Regressor:** Multi-tree bagging ensemble.
  3. **Ridge Regressor:** Regularized linear regression baseline.

> **🗣️ Presenter Script (45 Seconds):**  
> *"For our machine learning layer, we followed strict ML best practices: data was split into an 80% train and 20% test set BEFORE any scaling or vectorization to prevent data leakage. We benchmarked four distinct classification families for job domain prediction and three regression models for salary estimation. While ensemble methods like Random Forest performed well, Multinomial Logistic Regression was chosen for classification because its calibrated probability distributions allow us to recommend secondary career transition paths. For salary prediction, Gradient Boosting Regressor proved vastly superior in handling non-linear skill bonuses."*

---

## SLIDE 9: RESULTS & PERFORMANCE EVALUATION
* **Job Classifier Benchmarks (Test Set $N=200$):**
  * **Test Accuracy:** **1.00 (100%)**
  * **Macro Precision / Recall / F1-Score:** **1.00 / 1.00 / 1.00**
  * **Multi-Class ROC-AUC:** **1.00** across all 5 domains.
  * **Confusion Matrix:** Zero misclassifications across Backend, Cloud, Data Science, Frontend, and Mobile.
* **Salary Regressor Benchmarks:**
  * **Test $R^2$ Score:** **0.9945** (5-Fold CV $R^2 = 0.9925$)
  * **Mean Absolute Error (MAE):** **0.4189 LPA** (less than **₹41,900 error margin** on 4–30+ LPA salaries!)
  * **Root Mean Squared Error (RMSE):** **0.5581 LPA**
  * Outperformed Ridge Linear Regression ($R^2 = 0.8657$, MAE = 2.24 LPA) by over 80% in precision.
* **System Latency & Reliability:**
  * 118 out of 118 automated integration tests passing (100% verification rate).
  * Average end-to-end evaluation latency: **< 1.8 seconds**.

> **🗣️ Presenter Script (60 Seconds):**  
> *"Our experimental results validate the power of combining resume text with empirical test scores. In job classification, our model achieved 100% accuracy and an ROC-AUC of 1.00 on the test set, with zero misclassifications in the confusion matrix. For salary prediction, the Gradient Boosting Regressor achieved an extraordinary R-squared of 0.9945 with a Mean Absolute Error of just 0.4189 LPA. That means our model's salary prediction is accurate to within approximately ₹41,000 across candidate packages ranging from 4 to 30 LPA. Notice how linear Ridge regression failed with over 2.2 LPA error, proving that compensation curves in the tech industry are fundamentally non-linear."*

---

## SLIDE 10: USER EXPERIENCE & LIVE DASHBOARD
* **The 4-Step Interactive Candidate Journey:**
  * **Step 1: Upload Resume:** Drag-and-drop PDF/DOCX/Image with live OCR feedback and instant contact profile card.
  * **Step 2: Skill Selector:** Candidate reviews High vs. Medium confidence skills, toggles targets, and initiates exam.
  * **Step 3: 90-Minute Timed Assessment:** Live countdown HUD, Monaco-style Python code editor, and "Test with AI" instant feedback.
  * **Step 4: Career & Salary Dashboard:**
    * Executive scorecard (MCQ accuracy, coding score, test duration).
    * Primary job domain badge with confidence percentage.
    * **Career Switch Recommendations:** Suggests alternative domains with exact **missing skill gap pills** (e.g., `"Need Docker & Kubernetes to switch from Backend to Cloud"`).
    * **Salary Package Display:** CTC estimate (e.g. ₹16.5 LPA), confidence range (₹14.8 – ₹18.2 LPA), and compensation tier.

> **🗣️ Presenter Script (60 Seconds):**  
> *"From a user experience standpoint, ResuListic is built as an intuitive four-step journey. The candidate uploads their resume, reviews their extracted skills, enters a 90-minute timed testing environment with an integrated code editor, and receives a comprehensive executive dashboard. The dashboard doesn't just give a pass/fail; it provides deep career intelligence: showing their primary domain, secondary career switch recommendations, the exact missing skills needed to bridge the gap, and an itemized breakdown of their predicted market salary package."*

---

## SLIDE 11: CONCLUSION & FUTURE SCOPE
* **Conclusion:**
  * Successfully demonstrated that combining multimodal parsing, LLM-as-a-Judge code grading, and supervised ML creates an objective, cheat-resistant, and transparent recruitment platform.
  * Solves keyword stuffing and unverified claims on static resumes.
  * Delivers high-precision career domain matching and market salary calibration.
* **Future Scope:**
  * **1. Real-Time Voice Interviewer:** Leverage Gemini Live API over WebSockets for conversational technical viva rounds.
  * **2. Anti-Cheat & Proctoring Telemetry:** In-browser keystroke cadence, tab-switching detection, and webcam monitoring.
  * **3. Vector Semantic Job Requisition Matching:** Index real corporate job postings using text embeddings in MongoDB Atlas Vector Search.
  * **4. Generative Resume Optimizer:** Suggest tailored resume improvements based on assessment strengths and weaknesses.

> **🗣️ Presenter Script (45 Seconds):**  
> *"In conclusion, ResuListic proves that modern AI can transform recruitment from a superficial keyword search into a dynamic, empirical appraisal system. For future work, we plan to integrate real-time voice interviews using the Gemini Live API for conversational rounds, incorporate in-browser proctoring telemetry to prevent cheating, and connect with live corporate job feeds via vector semantic search. Thank you for your time, and we are now ready to demonstrate the live system and answer your questions."*

---

## SLIDE 12: REFERENCES & LIVE DEMO
* **Key References:**
  * Pedregosa et al. (2011) — *Scikit-learn: Machine Learning in Python*
  * Zheng et al. (2023) — *Judging LLM-as-a-Judge with MT-Bench (NeurIPS)*
  * Honnibal & Montani (2017) — *spaCy: Natural Language Understanding*
  * Smith (2007) — *An Overview of the Tesseract OCR Engine*
  * Gaur & Bansal (2023) — *Predictive Modeling of Software Engineer Compensation*
* **Live System Demo Links:**
  * **Localhost URL:** `http://localhost:8000`
  * **Docker Container:** `resulistic-app` (FastAPI + React 18 SPA)
  * **Public Tunnel:** `https://mortgages-condition-universal-fly.trycloudflare.com`

> **🗣️ Presenter Script (30 Seconds):**  
> *"Our codebase is fully containerized in Docker, backed by 118 automated tests, and accessible right now locally at localhost:8000 as well as through our public live link. We would love to walk you through a live demonstration of uploading a resume, taking a test, and generating the career intelligence report."*
