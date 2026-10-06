import React, { useState } from 'react';
import axios from 'axios';

const API_BASE = "http://localhost:8000";

const UploadResume = ({ userId, onUploadSuccess }) => {
    const [file, setFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [status, setStatus] = useState("");

    const handleFileChange = (e) => {
        if(e.target.files[0]) {
            setFile(e.target.files[0]);
            setStatus("");
        }
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) {
           setStatus("❌ Please select a PDF or DOCX file first!");
            return;
        }

        setIsUploading(true);
        setStatus("🚀 AI is analyzing your document...");

        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', userId);

        try {
            const response = await axios.post(`${API_BASE}/api/parse-resume`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            setIsUploading(false);
            setStatus(`✅ Success! Profile extracted: ${response.data.data.profile.name}`);
            setStatus(`✅ Success! Profile extracted: ${response.data.data.profile.name}`);
            // Trigger the next step in App.js
            if (onUploadSuccess) onUploadSuccess();
        } catch (error) {
            setIsUploading(false);
            setStatus(`❌ Upload failed. Make sure backend is running.`);
            
            // Temporary fix: UI check karne ke liye error aane par bhi Step 2 khol do
            if (onUploadSuccess) {
                setTimeout(() => {
                    onUploadSuccess();
                }, 1000); // 1 second ka delay taaki user error padh sake
            }
        }
    };

    return (
        <div className="glass-card">
            <span className="step-badge">Step 1</span>
            <h2 className="card-title">Upload Your Resume</h2>
            
            <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
                
                {/* Modern Drag & Drop Zone */}
                <div style={{ 
                    border: file ? '2px solid #38bdf8' : '2px dashed rgba(56, 189, 248, 0.4)', 
                    borderRadius: '16px', 
                    padding: '40px 20px', 
                    textAlign: 'center',
                    backgroundColor: file ? 'rgba(56, 189, 248, 0.05)' : 'rgba(15, 23, 42, 0.4)',
                    transition: 'all 0.3s ease',
                    position: 'relative',
                    cursor: 'pointer'
                }}>
                    {/* Hide default ugly input file button */}
                    <input 
                        type="file" 
                        accept=".pdf,.docx" 
                        onChange={handleFileChange} 
                        style={{ 
                            position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', 
                            opacity: 0, cursor: 'pointer' 
                        }} 
                    />
                    
                    <div style={{ pointerEvents: 'none' }}>
                        {/* Custom SVG Icon */}
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke={file ? "#38bdf8" : "#64748b"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '15px' }}>
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" y1="3" x2="12" y2="15"></line>
                        </svg>
                        <h3 style={{ color: '#f1f5f9', fontSize: '1.15rem', marginBottom: '8px', fontWeight: '500' }}>
                            {file ? file.name : "Click or drag your resume here"}
                        </h3>
                        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
                            {file ? "File selected and ready to parse" : "Supports PDF, DOCX (Max 5MB)"}
                        </p>
                    </div>
                </div>

                <button 
                    type="submit" 
                    disabled={isUploading}
                    className="btn-primary"
                >
                    {isUploading ? 'Extracting Data...' : 'Upload & Parse Resume'}
                </button>
            </form>
            
            {/* Clean Status Message Box */}
            {status && (
                <div style={{ 
                    marginTop: '25px', 
                    padding: '16px', 
                    borderRadius: '12px', 
                    backgroundColor: status.includes('❌') ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)', 
                    color: status.includes('❌') ? '#f87171' : '#34d399', 
                    border: `1px solid ${status.includes('❌') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`,
                    fontSize: '0.95rem',
                    fontWeight: '500'
                }}>
                    {status}
                </div>
            )}
        </div>
    );
};

export default UploadResume;