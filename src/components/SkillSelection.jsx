import React, { useState } from 'react';
import axios from 'axios';

const API_BASE = "http://localhost:8000";

const SkillSelection = ({ userId = "user_123", onConfirm }) => {
    const [skills, setSkills] = useState({ high_confidence: [], medium_confidence: [] });
    const [selectedSkills, setSelectedSkills] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    // Fetch parsed skills from the backend
    const fetchSkills = async () => {
        setLoading(true);
        setError("");
        try {
            const response = await axios.get(`${API_BASE}/api/user-skills/${userId}`);
            setSkills(response.data);
            // Default select all high confidence skills
            setSelectedSkills(response.data.high_confidence || []);
            setLoading(false);
        } catch (err) {
            // Fallback dummy data for UI testing if backend is offline
            const dummyHigh = ["React", "JavaScript", "Tailwind CSS"];
            const dummyMedium = ["Node.js", "Python", "MongoDB"];
            setSkills({
                high_confidence: dummyHigh,
                medium_confidence: dummyMedium
            });
            setSelectedSkills(dummyHigh); // Default select high confidence
            setLoading(false);
        }
    };

    // Handle checkbox change for skill selection
    const handleCheckboxChange = (skill) => {
        if (selectedSkills.includes(skill)) {
            setSelectedSkills(selectedSkills.filter(s => s !== skill));
        } else {
            setSelectedSkills([...selectedSkills, skill]);
        }
    };

    // Confirm and pass selected skills to App.js
    const handleConfirmSelection = () => {
        if (selectedSkills.length === 0) {
            alert("Please select at least one skill to proceed!");
            return;
        }
        if (onConfirm) {
            onConfirm(selectedSkills);
        }
    };

    return (
        <div className="glass-card">
            <span className="step-badge">Step 2</span>
            <h2 className="card-title">Verify Extracted Skills</h2>
            
            <button 
                onClick={fetchSkills} 
                disabled={loading}
                className="btn-primary"
                style={{ marginBottom: '25px' }}
            >
                {loading ? 'Analyzing Profile Data...' : 'Load Extracted Skills'}
            </button>

            {error && <p style={{ color: '#f87171' }}>{error}</p>}

            {/* High Confidence Matches Grid */}
            {skills.high_confidence && skills.high_confidence.length > 0 && (
                <div style={{ marginTop: '10px' }}>
                    <h3 style={{ fontSize: '1rem', color: '#34d399', marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#34d399', display: 'inline-block', boxShadow: '0 0 10px #34d399' }}></span>
                        High Confidence Matches
                    </h3>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
                        {skills.high_confidence.map(skill => (
                            <label key={skill} style={{ 
                                background: 'rgba(52, 211, 153, 0.1)', 
                                border: '1px solid rgba(52, 211, 153, 0.3)',
                                padding: '10px 18px', 
                                borderRadius: '25px', 
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '10px',
                                transition: 'all 0.3s ease',
                                color: '#f1f5f9'
                            }}>
                                <input 
                                    type="checkbox" 
                                    value={skill} 
                                    checked={selectedSkills.includes(skill)}
                                    onChange={() => handleCheckboxChange(skill)}
                                    style={{ accentColor: '#34d399', width: '16px', height: '16px' }} 
                                /> 
                                {skill}
                            </label>
                        ))}
                    </div>
                </div>
            )}

            {/* Medium Confidence Matches Grid */}
            {skills.medium_confidence && skills.medium_confidence.length > 0 && (
                <div style={{ marginTop: '35px' }}>
                    <h3 style={{ fontSize: '1rem', color: '#fbbf24', marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#fbbf24', display: 'inline-block', boxShadow: '0 0 10px #fbbf24' }}></span>
                        Medium Confidence Matches
                    </h3>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
                        {skills.medium_confidence.map(skill => (
                            <label key={skill} style={{ 
                                background: 'rgba(251, 191, 36, 0.1)', 
                                border: '1px solid rgba(251, 191, 36, 0.3)',
                                padding: '10px 18px', 
                                borderRadius: '25px', 
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '10px',
                                transition: 'all 0.3s ease',
                                color: '#f1f5f9'
                            }}>
                                <input 
                                    type="checkbox" 
                                    value={skill} 
                                    checked={selectedSkills.includes(skill)}
                                    onChange={() => handleCheckboxChange(skill)}
                                    style={{ accentColor: '#fbbf24', width: '16px', height: '16px' }} 
                                /> 
                                {skill}
                            </label>
                        ))}
                    </div>
                </div>
            )}

            {/* Confirm Selection Button */}
            {(skills.high_confidence.length > 0 || skills.medium_confidence.length > 0) && (
                <button 
                    onClick={handleConfirmSelection}
                    style={{ 
                        marginTop: '30px', 
                        width: '100%', 
                        padding: '14px', 
                        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 
                        color: 'white', 
                        border: 'none', 
                        borderRadius: '10px', 
                        cursor: 'pointer', 
                        fontWeight: '600',
                        fontSize: '1rem',
                        boxShadow: '0 4px 15px rgba(16, 185, 129, 0.3)'
                    }}
                >
                    Confirm Skills & Proceed to Test →
                </button>
            )}
        </div>
    );
};

export default SkillSelection;