import React, { useState, useRef } from 'react';
import axios from 'axios';

const API_BASE = "http://localhost:8000";

const UploadResume = ({ userId, onUploadSuccess }) => {
    const [file, setFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [status, setStatus] = useState("");
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef(null);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setStatus("");
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const droppedFile = e.dataTransfer.files[0];
            const ext = droppedFile.name.split('.').pop().toLowerCase();
            if (ext === 'pdf' || ext === 'docx') {
                setFile(droppedFile);
                setStatus("");
            } else {
                setStatus("❌ Please select a PDF or DOCX file first!");
            }
        }
    };

    const handleClearFile = (e) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        setFile(null);
        setStatus("");
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
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
            // Trigger the next step in App.js
            if (onUploadSuccess) onUploadSuccess();
        } catch (error) {
            setIsUploading(false);
            setStatus(`❌ Upload failed. Make sure backend is running.`);
            
            // Temporary fix: UI check karne ke liye error aane par bhi Step 2 khol do
            if (onUploadSuccess) {
                setTimeout(() => {
                    onUploadSuccess();
                }, 1000); // 1 second delay so user can read message
            }
        }
    };

    const formatFileSize = (bytes) => {
        if (!bytes || bytes === 0) return '0 B';
        const mb = bytes / (1024 * 1024);
        if (mb >= 1) {
            return `${mb.toFixed(2)} MB`;
        }
        const kb = bytes / 1024;
        return `${kb.toFixed(1)} KB`;
    };

    return (
        <div className="bg-white border border-slate-200/80 rounded-3xl p-6 sm:p-8 md:p-10 shadow-soft mb-8 transition-all duration-300">
            {/* Top Meta Header: Pill Badge & Info */}
            <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                <span className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-100 tracking-wide">
                    <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
                    Step 1 of 3
                </span>
                <span className="text-xs font-medium text-slate-400">
                    PDF or DOCX • Max 5MB
                </span>
            </div>

            {/* Approachable Heading */}
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-800 tracking-tight mb-2 font-poppins">
                Upload Your Resume
            </h2>
            <p className="text-sm sm:text-base text-slate-500 mb-8 leading-relaxed font-nunito">
                Let our friendly AI assistant scan your career background, extract your standout skills, and tailor personalized recommendations.
            </p>

            <form onSubmit={handleUpload} className="space-y-6">
                {/* Drag & Drop Zone */}
                <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`relative rounded-2xl border-2 border-dashed p-8 sm:p-10 text-center transition-all duration-200 ${
                        isDragging
                            ? 'border-sky-400 bg-sky-50/70 scale-[1.01]'
                            : file
                                ? 'border-emerald-300 bg-emerald-50/20'
                                : 'border-sky-200/90 hover:border-sky-300 bg-sky-50/30 hover:bg-sky-50/50'
                    }`}
                >
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.docx"
                        onChange={handleFileChange}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                        aria-label="Upload resume file (PDF or DOCX)"
                    />

                    <div className="flex flex-col items-center justify-center space-y-3 pointer-events-none">
                        {/* Approachable Pastel Circular Icon Container */}
                        <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors duration-200 ${
                            file ? 'bg-emerald-100 text-emerald-600' : 'bg-sky-100 text-sky-600'
                        }`}>
                            {file ? (
                                <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                                </svg>
                            ) : (
                                <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                            )}
                        </div>

                        {file ? (
                            <div className="space-y-1">
                                <p className="text-base font-semibold text-slate-800 break-all font-nunito">
                                    {file.name}
                                </p>
                                <p className="text-xs text-slate-500 font-medium">
                                    {formatFileSize(file.size)} • File ready for parsing
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-1">
                                <p className="text-base font-semibold text-slate-700 font-nunito">
                                    Click or drag your resume here
                                </p>
                                <p className="text-xs text-slate-400 font-normal">
                                    Supports PDF, DOCX (Max 5MB)
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Change / Clear File Pill Action */}
                    {file && (
                        <button
                            type="button"
                            onClick={handleClearFile}
                            className="absolute top-3 right-3 z-20 text-xs font-semibold text-slate-500 hover:text-rose-600 bg-white hover:bg-rose-50 rounded-full px-3 py-1.5 border border-slate-200 shadow-sm transition-colors cursor-pointer pointer-events-auto"
                        >
                            Change File
                        </button>
                    )}
                </div>

                {/* Fully Rounded Submit Button */}
                <button
                    type="submit"
                    disabled={isUploading}
                    className="w-full py-4 px-8 rounded-full font-semibold text-white bg-sky-600 hover:bg-sky-700 active:scale-[0.99] transition-all duration-200 shadow-md shadow-sky-600/20 disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none disabled:cursor-not-allowed flex items-center justify-center gap-2 cursor-pointer"
                >
                    {isUploading ? (
                        <>
                            <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                            </svg>
                            <span>AI is analyzing your document...</span>
                        </>
                    ) : (
                        <>
                            <span>Upload & Parse Resume</span>
                            <svg className="w-5 h-5 ml-1 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                            </svg>
                        </>
                    )}
                </button>
            </form>

            {/* Approachable Pastel Status Alert Box */}
            {status && (
                <div
                    role="alert"
                    className={`mt-6 p-4 rounded-2xl text-sm font-medium border flex items-start sm:items-center gap-3 transition-all ${
                        status.includes('❌')
                            ? 'bg-rose-50 text-rose-700 border-rose-200/80'
                            : status.includes('✅')
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
                                : 'bg-sky-50 text-sky-700 border-sky-200/80'
                    }`}
                >
                    <span className="text-base select-none">
                        {status.includes('❌') ? '⚠️' : status.includes('✅') ? '🎉' : '🚀'}
                    </span>
                    <span className="leading-snug">{status}</span>
                </div>
            )}
        </div>
    );
};

export default UploadResume;