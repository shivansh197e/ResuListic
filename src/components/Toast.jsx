import React from 'react';

const Toast = ({ message, type = 'success', onClose }) => {
    if (!message) return null;

    const isSuccess = type === 'success';

    return (
        <div style={{
            position: 'fixed',
            bottom: '30px',
            right: '30px',
            backgroundColor: isSuccess ? 'rgba(16, 185, 129, 0.9)' : 'rgba(239, 68, 68, 0.9)',
            backdropFilter: 'blur(10px)',
            color: 'white',
            padding: '14px 24px',
            borderRadius: '12px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            zIndex: 1000,
            animation: 'slideUp 0.3s ease',
            border: '1px solid rgba(255,255,255,0.2)',
            fontWeight: '500'
        }}>
            <span>{isSuccess ? '✅' : '❌'}</span>
            <span>{message}</span>
            <button 
                onClick={onClose} 
                style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'white',
                    fontSize: '16px',
                    cursor: 'pointer',
                    marginLeft: '10px'
                }}
            >
                ×
            </button>
        </div>
    );
};

export default Toast;