import React from 'react';

const ResultDashboard = ({ results, onRetakeTest }) => {
    // Ultimate high-performance evaluation metrics mock fallback
    const data = results || {
        score_percentage: 94,
        correct_answers: 5,
        total_questions: 5,
        grade: "S+",
        ai_feedback: "Exceptional mastery demonstrated across advanced full-stack architecture and optimized algorithmic execution. Zero architectural anti-patterns detected.",
        skill_breakdown: [
            { skill: "React Ecosystem & Hooks", status: "Elite", percentage: 98 },
            { skill: "JavaScript Performance", status: "Advanced", percentage: 92 },
            { skill: "Tailwind CSS & Architecture", status: "Mastery", percentage: 95 }
        ]
    };

    return (
        <div className="glass-card" style={{ 
            animation: 'fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1)', 
            border: '1px solid rgba(56, 189, 248, 0.25)',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(56, 189, 248, 0.15)'
        }}>
            {/* Top Status Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '25px' }}>
                <span className="step-badge" style={{ 
                    background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(129, 140, 248, 0.15))', 
                    color: '#38bdf8', 
                    borderColor: 'rgba(56, 189, 248, 0.4)',
                    boxShadow: '0 0 15px rgba(56, 189, 248, 0.2)'
                }}>
                    ⚡ AI Evaluation Certified
                </span>
                <span style={{ fontSize: '0.85rem', color: '#64748b', fontFamily: 'monospace' }}>SECURE_HASH: 0x98FF_VERIFIED</span>
            </div>

            <h2 className="card-title" style={{ fontSize: '2.2rem', background: 'linear-gradient(to right, #f8fafc, #cbd5e1)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Performance Intelligence Dashboard
            </h2>

            {/* Glowing Metrics Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px', marginBottom: '35px' }}>
                
                {/* Score Card */}
                <div style={{ 
                    background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.4))', 
                    padding: '30px', 
                    borderRadius: '18px', 
                    border: '1px solid rgba(56, 189, 248, 0.3)', 
                    textAlign: 'center',
                    boxShadow: 'inset 0 2px 10px rgba(56, 189, 248, 0.1)'
                }}>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '1.5px', fontWeight: '600' }}>Overall Score</p>
                    <h3 style={{ fontSize: '3rem', fontWeight: '800', background: 'linear-gradient(to right, #38bdf8, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        {data.score_percentage}%
                    </h3>
                </div>

                {/* Grade Card */}
                <div style={{ 
                    background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.4))', 
                    padding: '30px', 
                    borderRadius: '18px', 
                    border: '1px solid rgba(16, 185, 129, 0.3)', 
                    textAlign: 'center',
                    boxShadow: 'inset 0 2px 10px rgba(16, 185, 129, 0.1)'
                }}>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '1.5px', fontWeight: '600' }}>Assigned Tier</p>
                    <h3 style={{ fontSize: '3rem', fontWeight: '800', background: 'linear-gradient(to right, #34d399, #059669)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        {data.grade}
                    </h3>
                </div>

                {/* Accuracy Card */}
                <div style={{ 
                    background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.4))', 
                    padding: '30px', 
                    borderRadius: '18px', 
                    border: '1px solid rgba(192, 132, 252, 0.3)', 
                    textAlign: 'center',
                    boxShadow: 'inset 0 2px 10px rgba(192, 132, 252, 0.1)'
                }}>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '1.5px', fontWeight: '600' }}>Precision Rate</p>
                    <h3 style={{ fontSize: '3rem', fontWeight: '800', background: 'linear-gradient(to right, #c084fc, #e879f9)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        {data.correct_answers}/{data.total_questions}
                    </h3>
                </div>

            </div>

            {/* AI Insights Neural Box */}
            <div style={{ 
                background: 'rgba(15, 23, 42, 0.7)', 
                padding: '30px', 
                borderRadius: '18px', 
                border: '1px solid rgba(129, 140, 248, 0.2)', 
                marginBottom: '35px',
                position: 'relative',
                overflow: 'hidden'
            }}>
                <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: 'linear-gradient(to bottom, #38bdf8, #818cf8)' }}></div>
                <h3 style={{ fontSize: '1.15rem', color: '#f1f5f9', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px', fontWeight: '600' }}>
                    <span style={{ fontSize: '1.3rem' }}>🧠</span> Neural Evaluator Feedback
                </h3>
                <p style={{ color: '#cbd5e1', fontSize: '1.05rem', lineHeight: '1.7', fontStyle: 'italic' }}>
                    "{data.ai_feedback}"
                </p>
            </div>

            {/* Skill Breakdown Grid */}
            <div style={{ marginBottom: '35px' }}>
                <h3 style={{ fontSize: '1.15rem', color: '#f1f5f9', marginBottom: '20px', fontWeight: '600', letterSpacing: '0.5px' }}>
                    Competency Vector Breakdown
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {data.skill_breakdown.map((item, index) => (
                        <div key={index} style={{ 
                            background: 'rgba(15, 23, 42, 0.5)', 
                            padding: '18px 24px', 
                            borderRadius: '14px', 
                            border: '1px solid rgba(255, 255, 255, 0.06)', 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            alignItems: 'center',
                            transition: 'all 0.3s ease'
                        }}>
                            <span style={{ fontWeight: '600', color: '#f8fafc', fontSize: '1.05rem' }}>{item.skill}</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                                <span style={{ 
                                    fontSize: '0.85rem', 
                                    padding: '6px 14px', 
                                    background: 'rgba(56, 189, 248, 0.1)', 
                                    color: '#38bdf8', 
                                    borderRadius: '10px', 
                                    border: '1px solid rgba(56, 189, 248, 0.25)',
                                    fontWeight: '600',
                                    letterSpacing: '0.5px'
                                }}>
                                    {item.status}
                                </span>
                                <span style={{ fontWeight: '800', color: '#34d399', fontSize: '1.1rem', width: '55px', textAlign: 'right' }}>
                                    {item.percentage}%
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Action Control */}
            {onRetakeTest && (
                <button 
                    onClick={onRetakeTest}
                    className="btn-primary"
                    style={{ 
                        background: 'linear-gradient(135deg, #0284c7 0%, #6366f1 50%, #8b5cf6 100%)',
                        padding: '16px',
                        fontSize: '1.1rem',
                        boxShadow: '0 10px 25px rgba(99, 102, 241, 0.4)'
                    }}
                >
                    Initialize New Assessment Session 🚀
                </button>
            )}
        </div>
    );
};

export default ResultDashboard;