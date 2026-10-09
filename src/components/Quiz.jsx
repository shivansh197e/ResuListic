import React, { useState } from 'react';
import axios from 'axios';
import ResultDashboard from './ResultDashboard'; // Humne dashboard import kar liya

const API_BASE = "http://localhost:8000";

const Quiz = ({ userId = "user_123", selectedSkills = ["React", "JavaScript"] }) => {
    const [testSession, setTestSession] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [currentQIndex, setCurrentQIndex] = useState(0);
    const [answers, setAnswers] = useState({});
    const [isSubmitted, setIsSubmitted] = useState(false); // Nayi state dashboard dikhane ke liye

    // Initialize dynamic test session based on selected skills
    const handleStartTest = async () => {
        setLoading(true);
        setError("");
        try {
            const response = await axios.post(`${API_BASE}/api/start-test`, {
                user_id: userId,
                selected_skills: selectedSkills
            });
            setTestSession(response.data);
            setLoading(false);
        } catch (err) {
            // Dummy session data
            setTestSession({
                session_id: "SESSION_ALPHA_099",
                total_questions: 2,
                questions: [
                    { id: 1, type: "mcq", text: "Which hook is used to manage state in a React functional component?", options: ["useEffect()", "useState()", "useContext()", "useReducer()"] },
                    { id: 2, type: "coding", text: "Write an optimized JavaScript function to reverse a string in O(n) time complexity." }
                ]
            });
            setLoading(false);
        }
    };

    const handleAnswer = (val) => {
        setAnswers({ ...answers, [currentQIndex]: val });
    };

    // Yahan alert ki jagah hum state true kar rahe hain
    const submitTest = async () => {
        setIsSubmitted(true);
    };

    // Agar test submit ho gaya, toh seedha Dashboard dikhao
    if (isSubmitted) {
        return <ResultDashboard onRetakeTest={() => {
            setIsSubmitted(false);
            setTestSession(null);
            setAnswers({});
            setCurrentQIndex(0);
        }} />;
    }

    const currentQuestion = testSession?.questions?.[currentQIndex];
    const totalQuestions = testSession?.questions?.length || 0;
    const progressPercent = totalQuestions > 0 ? Math.round(((currentQIndex + 1) / totalQuestions) * 100) : 0;

    return (
        <div className="bg-white rounded-3xl p-7 sm:p-9 border border-slate-100 shadow-soft transition-all duration-300">
            {/* Top Step Badge */}
            <div className="flex items-center justify-between gap-3 mb-4">
                <span className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-bold tracking-wide uppercase bg-sky-50 text-sky-600 border border-sky-100 shadow-sm font-nunito">
                    <span className="w-2 h-2 rounded-full bg-sky-400"></span>
                    Step 3 • Assessment
                </span>
                {testSession && (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-slate-50 text-slate-500 border border-slate-200">
                        <span className="text-slate-400">ID:</span>
                        <span className="text-sky-600 font-semibold">{testSession.session_id}</span>
                    </span>
                )}
            </div>

            {/* Title & Friendly Subtitle */}
            <h2 className="text-2xl sm:text-3xl font-bold font-poppins text-slate-800 tracking-tight mb-2">
                Dynamic AI Assessment
            </h2>
            <p className="text-slate-500 font-nunito text-sm sm:text-base leading-relaxed mb-6">
                Test your technical proficiency with tailored AI questions curated from your verified skill set.
            </p>

            {!testSession ? (
                <div className="space-y-6">
                    {/* Skills Summary Pills */}
                    {selectedSkills && selectedSkills.length > 0 && (
                        <div className="p-4 sm:p-5 rounded-2xl bg-slate-50/80 border border-slate-100">
                            <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 font-nunito">
                                Verified Skills Under Evaluation
                            </p>
                            <div className="flex flex-wrap items-center gap-2">
                                {selectedSkills.map((skill, idx) => (
                                    <span 
                                        key={idx} 
                                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/70 font-nunito shadow-sm"
                                    >
                                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                                        {skill}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Informational Callout */}
                    <div className="p-5 rounded-2xl bg-sky-50/60 border border-sky-100 text-slate-600 font-nunito text-sm leading-relaxed flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-sky-100 text-sky-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <div>
                            <p className="font-semibold text-slate-800 mb-0.5">Ready to begin?</p>
                            <p className="text-slate-600">
                                You will complete multiple choice and practical coding challenges. Take your time to review your answers before submitting.
                            </p>
                        </div>
                    </div>

                    {/* Start Assessment CTA Button */}
                    <button 
                        onClick={handleStartTest} 
                        disabled={loading}
                        className="w-full py-4 px-6 rounded-full bg-sky-500 hover:bg-sky-600 active:bg-sky-700 text-white font-nunito font-semibold text-base sm:text-lg shadow-soft hover:shadow-soft-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2.5 transform hover:-translate-y-0.5 active:translate-y-0"
                    >
                        {loading ? (
                            <>
                                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span>Compiling Question Bank...</span>
                            </>
                        ) : (
                            <>
                                <span>Start Technical Evaluation</span>
                                <svg className="w-5 h-5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                </svg>
                            </>
                        )}
                    </button>

                    {error && (
                        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-100 text-rose-600 text-sm font-medium flex items-center gap-2 font-nunito">
                            <span>⚠️</span>
                            <span>{error}</span>
                        </div>
                    )}
                </div>
            ) : (
                <div className="space-y-6">
                    {/* Stepper Progress Bar Header */}
                    <div className="bg-slate-50/70 p-4 sm:p-5 rounded-2xl border border-slate-100 space-y-3">
                        <div className="flex items-center justify-between text-xs sm:text-sm font-nunito">
                            <div className="flex items-center gap-2">
                                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-sky-100 text-sky-700">
                                    {currentQuestion.type === 'mcq' ? 'Multiple Choice' : 'Coding Challenge'}
                                </span>
                            </div>
                            <span className="font-bold text-slate-700">
                                Question {currentQIndex + 1} of {totalQuestions}
                            </span>
                        </div>

                        {/* Progress bar track & indicator */}
                        <div className="w-full h-2.5 bg-slate-200/70 rounded-full overflow-hidden">
                            <div 
                                className="h-full bg-gradient-to-r from-sky-400 via-teal-400 to-emerald-400 rounded-full transition-all duration-300 ease-out"
                                style={{ width: `${progressPercent}%` }}
                            ></div>
                        </div>

                        {/* Progress Stepper Pills */}
                        <div className="flex items-center justify-between text-xs text-slate-400 font-nunito pt-1">
                            <span>Progress: {progressPercent}%</span>
                            <div className="flex items-center gap-1.5">
                                {testSession.questions.map((_, idx) => (
                                    <span
                                        key={idx}
                                        className={`w-2 h-2 rounded-full transition-all duration-200 ${
                                            idx === currentQIndex
                                                ? 'w-6 bg-sky-500'
                                                : answers[idx] !== undefined
                                                ? 'bg-emerald-400'
                                                : 'bg-slate-200'
                                        }`}
                                    ></span>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Question Card Box */}
                    <div className="p-6 sm:p-8 bg-slate-50/60 rounded-2xl border border-slate-100 min-h-[220px]">
                        <div className="flex items-start gap-3 mb-6">
                            <span className="w-7 h-7 rounded-full bg-sky-100 text-sky-700 font-bold text-xs flex items-center justify-center font-nunito flex-shrink-0 mt-0.5">
                                {currentQIndex + 1}
                            </span>
                            <p className="text-base sm:text-lg font-semibold font-poppins text-slate-800 leading-relaxed">
                                {currentQuestion.text}
                            </p>
                        </div>

                        {/* MCQ Options with approachable styling and soft active highlight */}
                        {currentQuestion.type === "mcq" && (
                            <div className="space-y-3">
                                {currentQuestion.options.map((opt, i) => {
                                    const isSelected = answers[currentQIndex] === opt;
                                    return (
                                        <label 
                                            key={i} 
                                            className={`group relative flex items-center gap-3.5 p-4 rounded-2xl border cursor-pointer transition-all duration-200 ${
                                                isSelected 
                                                    ? 'bg-sky-50/90 border-sky-300 ring-2 ring-sky-100 text-sky-950 shadow-sm' 
                                                    : 'bg-white border-slate-200/80 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700'
                                            }`}
                                        >
                                            <input 
                                                type="radio" 
                                                name="mcq_option" 
                                                value={opt} 
                                                onChange={(e) => handleAnswer(e.target.value)} 
                                                checked={isSelected} 
                                                className="sr-only"
                                            />
                                            {/* Custom Approachable Radio Circle */}
                                            <div className={`w-5 h-5 rounded-full border flex items-center justify-center flex-shrink-0 transition-colors ${
                                                isSelected 
                                                    ? 'border-sky-500 bg-sky-500' 
                                                    : 'border-slate-300 bg-white group-hover:border-slate-400'
                                            }`}>
                                                {isSelected && <span className="w-2 h-2 rounded-full bg-white"></span>}
                                            </div>
                                            <span className={`text-sm sm:text-base font-nunito leading-normal select-none ${
                                                isSelected ? 'font-semibold text-sky-950' : 'text-slate-700'
                                            }`}>
                                                {opt}
                                            </span>
                                        </label>
                                    );
                                })}
                            </div>
                        )}

                        {/* Coding Editor with Clean, Approachable Light/Subtle Monospace Styling */}
                        {currentQuestion.type === "coding" && (
                            <div className="space-y-2">
                                <div className="flex items-center justify-between text-xs text-slate-500 px-1 font-mono">
                                    <div className="flex items-center gap-2">
                                        <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block"></span>
                                        <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block"></span>
                                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block"></span>
                                        <span className="ml-1 text-slate-600 font-sans font-medium text-xs">Solution Code</span>
                                    </div>
                                    <span className="text-slate-400 font-mono text-[11px]">JavaScript (ES6)</span>
                                </div>
                                <textarea 
                                    rows="9" 
                                    className="w-full p-4 sm:p-5 bg-white font-mono text-sm text-slate-800 rounded-2xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-200 focus:border-sky-400 transition-all resize-y shadow-inner-soft leading-relaxed placeholder:text-slate-400"
                                    placeholder="// Write your optimized solution here..." 
                                    value={answers[currentQIndex] || ""} 
                                    onChange={(e) => handleAnswer(e.target.value)}
                                ></textarea>
                                <p className="text-xs text-slate-400 font-nunito italic px-1">
                                    Tip: Provide your algorithmic solution with attention to time and space complexity.
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Navigation Buttons: Previous, Next, Submit */}
                    <div className="flex items-center justify-between gap-3 pt-2">
                        <button 
                            disabled={currentQIndex === 0} 
                            onClick={() => setCurrentQIndex(currentQIndex - 1)} 
                            className="px-6 py-2.5 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-800 font-nunito font-semibold text-sm transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-slate-600 flex items-center gap-2"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                            </svg>
                            <span>Previous</span>
                        </button>

                        {currentQIndex < totalQuestions - 1 ? (
                            <button 
                                onClick={() => setCurrentQIndex(currentQIndex + 1)} 
                                className="px-7 py-2.5 rounded-full bg-sky-500 hover:bg-sky-600 active:bg-sky-700 text-white font-nunito font-semibold text-sm shadow-soft hover:shadow-soft-md transition-all duration-200 flex items-center gap-2 transform active:scale-95"
                            >
                                <span>Next</span>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                </svg>
                            </button>
                        ) : (
                            <button 
                                onClick={submitTest} 
                                className="px-8 py-2.5 rounded-full bg-emerald-500 hover:bg-emerald-600 active:bg-emerald-700 text-white font-nunito font-semibold text-sm shadow-soft hover:shadow-soft-md transition-all duration-200 flex items-center gap-2 transform active:scale-95"
                            >
                                <span>Submit Test</span>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                            </button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default Quiz;