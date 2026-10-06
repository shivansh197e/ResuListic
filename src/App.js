import React, { useState } from 'react';
import './App.css';
import UploadResume from './components/UploadResume';
import SkillSelection from './components/SkillSelection';
import Quiz from './components/Quiz';
import Toast from './components/Toast'; // Import the new Toast component

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
    <div className="app-container">
      <h1 className="app-title">Resulistic.</h1>
      
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
  );
}

export default App;