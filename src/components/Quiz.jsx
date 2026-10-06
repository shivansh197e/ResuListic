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

    return (
        <div className="glass-card">
            <span className="step-badge">Step 3</span>
            <h2 className="card-title">Dynamic AI Assessment</h2>

            {!testSession ? (
                <div>
                    <button 
                        onClick={handleStartTest} 
                        disabled={loading}
                        className="btn-primary"
                    >
                        {loading ? 'Compiling Question Bank...' : 'Start Technical Evaluation'}
                    </button>
                    {error && <p style={{ color: '#f87171', marginTop: '15px' }}>{error}</p>}
                </div>
            ) : (
                <div style={{ marginTop: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', paddingBottom: '15px', borderBottom: '1px solid rgba(255,255,255,0.08)', marginBottom: '25px' }}>
                        <span style={{ fontSize: '0.9rem', letterSpacing: '0.5px' }}>SESSION_ID: <span style={{ color: '#818cf8', fontWeight: '600' }}>{testSession.session_id}</span></span>
                        <span style={{ fontSize: '0.9rem', fontWeight: 'bold', color: '#f1f5f9' }}>Question {currentQIndex + 1} of {testSession.questions.length}</span>
                    </div>

                    <div style={{ padding: '30px', backgroundColor: 'rgba(15, 23, 42, 0.7)', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.05)', minHeight: '240px' }}>
                        <p style={{ fontSize: '1.15rem', marginBottom: '25px', fontWeight: '500', color: '#f8fafc', lineHeight: '1.6' }}>
                            {testSession.questions[currentQIndex].text}
                        </p>

                        {testSession.questions[currentQIndex].type === "mcq" && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                                {testSession.questions[currentQIndex].options.map((opt, i) => (
                                    <label key={i} style={{ 
                                        cursor: 'pointer', 
                                        padding: '16px 20px', 
                                        backgroundColor: answers[currentQIndex] === opt ? 'rgba(56, 189, 248, 0.1)' : 'rgba(30, 41, 59, 0.4)', 
                                        borderRadius: '12px', 
                                        border: answers[currentQIndex] === opt ? '1px solid #38bdf8' : '1px solid rgba(255,255,255,0.08)',
                                        transition: 'all 0.2s',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '15px'
                                    }}>
                                        <input 
                                            type="radio" 
                                            name="mcq_option" 
                                            value={opt} 
                                            onChange={(e) => handleAnswer(e.target.value)} 
                                            checked={answers[currentQIndex] === opt} 
                                            style={{ width: '20px', height: '20px', accentColor: '#38bdf8' }}
                                        />
                                        <span style={{ fontSize: '1.05rem', color: answers[currentQIndex] === opt ? '#38bdf8' : '#cbd5e1' }}>{opt}</span>
                                    </label>
                                ))}
                            </div>
                        )}

                        {testSession.questions[currentQIndex].type === "coding" && (
                            <textarea 
                                rows="10" 
                                style={{ 
                                    width: '100%', 
                                    padding: '20px', 
                                    backgroundColor: '#020617', 
                                    color: '#38bdf8', 
                                    fontFamily: '"Consolas", "Courier New", monospace', 
                                    border: '1px solid rgba(56, 189, 248, 0.2)', 
                                    borderRadius: '12px',
                                    fontSize: '0.95rem',
                                    resize: 'vertical',
                                    outline: 'none',
                                    boxShadow: 'inset 0 4px 15px rgba(0,0,0,0.6)',
                                    lineHeight: '1.5'
                                }} 
                                placeholder="// Write your optimized solution here..." 
                                value={answers[currentQIndex] || ""} 
                                onChange={(e) => handleAnswer(e.target.value)}
                            ></textarea>
                        )}
                    </div>

                    <div style={{ marginTop: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <button 
                            disabled={currentQIndex === 0} 
                            onClick={() => setCurrentQIndex(currentQIndex - 1)} 
                            style={{ 
                                padding: '12px 24px', 
                                backgroundColor: 'transparent', 
                                color: currentQIndex === 0 ? '#475569' : '#94a3b8', 
                                border: currentQIndex === 0 ? '1px solid #334155' : '1px solid #475569', 
                                borderRadius: '10px', 
                                cursor: currentQIndex === 0 ? 'not-allowed' : 'pointer',
                                fontWeight: '600',
                                transition: 'all 0.2s'
                            }}
                        >
                            ← Previous
                        </button>

                        {currentQIndex < testSession.questions.length - 1 ? (
                            <button 
                                onClick={() => setCurrentQIndex(currentQIndex + 1)} 
                                style={{ 
                                    padding: '12px 30px', 
                                    backgroundColor: 'rgba(56, 189, 248, 0.1)', 
                                    color: '#38bdf8', 
                                    border: '1px solid rgba(56, 189, 248, 0.3)', 
                                    borderRadius: '10px', 
                                    cursor: 'pointer',
                                    fontWeight: '600',
                                    transition: 'all 0.2s'
                                }}
                            >
                                Next →
                            </button>
                        ) : (
                            <button 
                                onClick={submitTest} 
                                style={{ 
                                    padding: '12px 35px', 
                                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 
                                    color: 'white', 
                                    border: 'none', 
                                    borderRadius: '10px', 
                                    cursor: 'pointer',
                                    fontWeight: '600',
                                    boxShadow: '0 4px 15px rgba(16, 185, 129, 0.3)'
                                }}
                            >
                                Submit Test
                            </button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default Quiz;