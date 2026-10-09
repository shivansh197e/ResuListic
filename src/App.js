import React, { useState } from 'react';
import './App.css';
import UploadResume from './components/UploadResume';
import SkillSelection from './components/SkillSelection';
import Quiz from './components/Quiz';
import Toast from './components/Toast';

function App() {
  // Global state to manage user journey flow and toast notifications
  const [currentStep, setCurrentStep] = useState(1);
  const [verifiedSkills, setVerifiedSkills] = useState([]);
  const [toast, setToast] = useState({ message: '', type: 'success' });
  
  const userId = "user_123";

  // Helper function to trigger toast messages
  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast({ message: '', type: 'success' });
    }, 4000); // Auto hide after 4 seconds
  };

  // Triggered when resume upload succeeds
  const handleResumeUploaded = () => {
    setCurrentStep(2);
    showToast("Resume parsed and verified successfully!");
  };

  // Triggered when user confirms selected skills
  const handleSkillsConfirmed = (selectedSkills) => {
    setVerifiedSkills(selectedSkills);
    setCurrentStep(3);
    showToast("Skills locked successfully! Generating AI test...");
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans antialiased selection:bg-sky-100 selection:text-sky-800">
      <div className="app-container">
        {/* Friendly Approachable Header */}
        <header className="app-header">
          <div className="app-badge">
            <span className="app-badge-dot"></span>
            AI Career Assistant
          </div>
          <h1 className="app-title">
            Resu<span className="app-title-accent">Listic</span>
          </h1>
          <p className="app-subtitle">
            Upload your resume, verify your skills, and take an adaptive AI quiz for personalized career guidance.
          </p>
        </header>

        {/* Friendly Stepper Progress Bar */}
        <nav aria-label="Journey Progress" className="journey-stepper">
          <div className={`step-indicator ${currentStep === 1 ? 'active' : currentStep > 1 ? 'completed' : 'upcoming'}`}>
            <span>{currentStep > 1 ? '✓' : '1'}</span>
            <span>Upload Resume</span>
          </div>
          <div className={`step-indicator ${currentStep === 2 ? 'active' : currentStep > 2 ? 'completed' : 'upcoming'}`}>
            <span>{currentStep > 2 ? '✓' : '2'}</span>
            <span>Skill Verification</span>
          </div>
          <div className={`step-indicator ${currentStep === 3 ? 'active' : currentStep > 3 ? 'completed' : 'upcoming'}`}>
            <span>{currentStep > 3 ? '✓' : '3'}</span>
            <span>AI Assessment</span>
          </div>
        </nav>
        
        {/* Step 1: Upload Resume */}
        <UploadResume 
          userId={userId} 
          onUploadSuccess={handleResumeUploaded} 
        />
        
        {/* Step 2: Skill Selection */}
        {currentStep >= 2 && (
          <div style={{ animation: 'fadeIn 0.5s ease-in' }}>
            <SkillSelection 
              userId={userId} 
              onConfirm={handleSkillsConfirmed} 
            />
          </div>
        )}
        
        {/* Step 3: Dynamic AI Assessment */}
        {currentStep >= 3 && (
          <div style={{ animation: 'fadeIn 0.5s ease-in' }}>
            <Quiz 
              userId={userId} 
              selectedSkills={verifiedSkills} 
            />
          </div>
        )}
        
        {/* Global Toast Notification Component */}
        <Toast 
          message={toast.message} 
          type={toast.type} 
          onClose={() => setToast({ message: '', type: 'success' })} 
        />
      </div>
    </div>
  );
}

export default App;