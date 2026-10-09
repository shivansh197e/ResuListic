import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import UploadResume from '../components/UploadResume';
import Quiz from '../components/Quiz';
import ResultDashboard from '../components/ResultDashboard';
import axios from 'axios';

jest.mock('axios');

describe('Empirical Challenger Test Suite — ResuListic Redesign', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Contract 1: UploadResume onUploadSuccess & Resilience Fallback', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    test('Empirical: Successful upload triggers onUploadSuccess immediately', async () => {
      const mockSuccess = jest.fn();
      axios.post.mockResolvedValueOnce({
        data: {
          data: {
            profile: { name: 'Alex Johnson' }
          }
        }
      });

      render(<UploadResume userId="user_123" onUploadSuccess={mockSuccess} />);

      const fileInput = screen.getByLabelText(/upload resume file/i);
      const validFile = new File(['dummy resume'], 'resume.pdf', { type: 'application/pdf' });
      fireEvent.change(fileInput, { target: { files: [validFile] } });

      const submitBtn = screen.getByRole('button', { name: /Upload & Parse Resume/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(axios.post).toHaveBeenCalledTimes(1);
        expect(mockSuccess).toHaveBeenCalledTimes(1);
      });
    });

    test('Empirical: Network failure triggers 1000ms fallback before calling onUploadSuccess', async () => {
      const mockSuccess = jest.fn();
      axios.post.mockRejectedValueOnce(new Error('Network Error (Backend Offline)'));

      render(<UploadResume userId="user_123" onUploadSuccess={mockSuccess} />);

      const fileInput = screen.getByLabelText(/upload resume file/i);
      const validFile = new File(['dummy resume'], 'resume.pdf', { type: 'application/pdf' });
      fireEvent.change(fileInput, { target: { files: [validFile] } });

      const submitBtn = screen.getByRole('button', { name: /Upload & Parse Resume/i });
      fireEvent.click(submitBtn);

      // Verify network error message displayed
      await waitFor(() => {
        expect(screen.getByText(/Upload failed. Make sure backend is running/i)).toBeInTheDocument();
      });

      // Before 1000ms: onUploadSuccess should NOT have been called yet
      expect(mockSuccess).not.toHaveBeenCalled();

      // Advance timers by 1000ms
      act(() => {
        jest.advanceTimersByTime(1000);
      });

      // Now onUploadSuccess should have been called
      expect(mockSuccess).toHaveBeenCalledTimes(1);
    });

    test('Empirical: Omitting onUploadSuccess prop does not crash on error fallback', async () => {
      axios.post.mockRejectedValueOnce(new Error('Backend Offline'));

      render(<UploadResume userId="user_123" />);

      const fileInput = screen.getByLabelText(/upload resume file/i);
      const validFile = new File(['dummy resume'], 'resume.pdf', { type: 'application/pdf' });
      fireEvent.change(fileInput, { target: { files: [validFile] } });

      const submitBtn = screen.getByRole('button', { name: /Upload & Parse Resume/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Upload failed. Make sure backend is running/i)).toBeInTheDocument();
      });

      // Advance timers - should not throw unhandled exception
      act(() => {
        jest.advanceTimersByTime(1000);
      });
    });

    test('Empirical: Submitting without file displays error and does not call API or onUploadSuccess', async () => {
      const mockSuccess = jest.fn();
      render(<UploadResume userId="user_123" onUploadSuccess={mockSuccess} />);

      const submitBtn = screen.getByRole('button', { name: /Upload & Parse Resume/i });
      fireEvent.click(submitBtn);

      expect(screen.getByText(/Please select a PDF or DOCX file first!/i)).toBeInTheDocument();
      expect(axios.post).not.toHaveBeenCalled();
      expect(mockSuccess).not.toHaveBeenCalled();
    });
  });

  describe('Contract 2: Quiz -> ResultDashboard -> onRetakeTest Lifecycle', () => {
    test('Empirical: Backend offline gracefully loads 2 mock questions (1 MCQ, 1 coding)', async () => {
      axios.post.mockRejectedValueOnce(new Error('Backend Offline'));

      render(<Quiz userId="user_123" selectedSkills={['React', 'JavaScript']} />);

      // Initial state
      expect(screen.getByText(/Dynamic AI Assessment/i)).toBeInTheDocument();
      expect(screen.getByText('React')).toBeInTheDocument();
      expect(screen.getByText('JavaScript')).toBeInTheDocument();

      const startBtn = screen.getByRole('button', { name: /Start Technical Evaluation/i });
      await act(async () => {
        fireEvent.click(startBtn);
      });

      // Fallback session loaded
      expect(screen.getByText(/Which hook is used to manage state in a React functional component\?/i)).toBeInTheDocument();
      expect(screen.getByText(/Question 1 of 2/i)).toBeInTheDocument();
      expect(screen.getByText('SESSION_ALPHA_099')).toBeInTheDocument();
    });

    test('Empirical: Quiz submission transitions to ResultDashboard and onRetakeTest resets state', async () => {
      axios.post.mockRejectedValueOnce(new Error('Backend Offline'));

      render(<Quiz userId="user_123" selectedSkills={['React', 'JavaScript']} />);

      // Start quiz
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Start Technical Evaluation/i }));
      });

      // Answer Q1 (MCQ)
      const useStateRadio = screen.getByDisplayValue('useState()');
      fireEvent.click(useStateRadio);
      expect(useStateRadio.checked).toBe(true);

      // Navigate to Q2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));
      expect(screen.getByText(/Question 2 of 2/i)).toBeInTheDocument();

      // Answer Q2 (Coding)
      const textarea = screen.getByPlaceholderText(/\/\/ Write your optimized solution here\.\.\./i);
      fireEvent.change(textarea, { target: { value: 'const reverse = s => s.split("").reverse().join("");' } });

      // Submit test
      const submitBtn = screen.getByRole('button', { name: /Submit Test/i });
      fireEvent.click(submitBtn);

      // Contract check: Quiz renders ResultDashboard upon submit
      expect(screen.getByText(/Performance Intelligence Dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/AI Evaluation Certified/i)).toBeInTheDocument();

      // Retake test button resets Quiz state
      const retakeBtn = screen.getByRole('button', { name: /Initialize New Assessment Session/i });
      expect(retakeBtn).toBeInTheDocument();

      fireEvent.click(retakeBtn);

      // Verify quiz state reset: back to Start Technical Evaluation screen
      expect(screen.getByText(/Start Technical Evaluation/i)).toBeInTheDocument();
      expect(screen.queryByText(/Performance Intelligence Dashboard/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Question 1 of 2/i)).not.toBeInTheDocument();
    });
  });

  describe('Contract 3: ResultDashboard Resilience & Defensive Fallbacks', () => {
    test('Empirical: ResultDashboard safely uses fallback data when results prop is null/undefined', () => {
      render(<ResultDashboard results={null} onRetakeTest={jest.fn()} />);

      expect(screen.getByText('94%')).toBeInTheDocument();
      expect(screen.getByText('S+')).toBeInTheDocument();
      expect(screen.getByText('5/5')).toBeInTheDocument();
      expect(screen.getByText(/React Ecosystem & Hooks/i)).toBeInTheDocument();
      expect(screen.getByText(/Tailwind CSS & Architecture/i)).toBeInTheDocument();
    });

    test('Empirical: ResultDashboard accurately displays custom evaluation data', () => {
      const customData = {
        score_percentage: 75,
        correct_answers: 3,
        total_questions: 4,
        grade: 'B+',
        ai_feedback: 'Good problem-solving speed but review memory management.',
        skill_breakdown: [
          { skill: 'Algorithms', status: 'Intermediate', percentage: 70 },
          { skill: 'System Design', status: 'Proficient', percentage: 80 }
        ]
      };

      const mockRetake = jest.fn();
      render(<ResultDashboard results={customData} onRetakeTest={mockRetake} />);

      expect(screen.getByText('75%')).toBeInTheDocument();
      expect(screen.getByText('B+')).toBeInTheDocument();
      expect(screen.getByText('3/4')).toBeInTheDocument();
      expect(screen.getByText('"Good problem-solving speed but review memory management."')).toBeInTheDocument();
      expect(screen.getByText('Algorithms')).toBeInTheDocument();
      expect(screen.getByText('System Design')).toBeInTheDocument();

      const retakeBtn = screen.getByRole('button', { name: /Initialize New Assessment Session/i });
      fireEvent.click(retakeBtn);
      expect(mockRetake).toHaveBeenCalledTimes(1);
    });

    test('Empirical Adversarial Stress: Partial results object without skill_breakdown crashes without default guard', () => {
      // Stress test: what if backend returns partial result without skill_breakdown?
      const incompleteResults = {
        score_percentage: 80,
        correct_answers: 4,
        total_questions: 5,
        grade: 'A'
        // skill_breakdown is missing!
      };

      // We expect an error to be thrown because `data.skill_breakdown.length` is accessed without optional chaining
      expect(() => {
        render(<ResultDashboard results={incompleteResults} onRetakeTest={jest.fn()} />);
      }).toThrow();
    });
  });

  describe('Contract 4: Rounded Corners & Soft Styling Audit', () => {
    test('Empirical: All interactive buttons in UploadResume, Quiz, and ResultDashboard have rounded-full', async () => {
      // UploadResume button
      const { unmount: unmountUpload } = render(<UploadResume userId="u1" onUploadSuccess={jest.fn()} />);
      const uploadSubmitBtn = screen.getByRole('button', { name: /Upload & Parse Resume/i });
      expect(uploadSubmitBtn.className).toContain('rounded-full');
      unmountUpload();

      // Quiz button
      const { unmount: unmountQuiz } = render(<Quiz userId="u1" selectedSkills={['React']} />);
      const quizStartBtn = screen.getByRole('button', { name: /Start Technical Evaluation/i });
      expect(quizStartBtn.className).toContain('rounded-full');
      unmountQuiz();

      // ResultDashboard button
      const { unmount: unmountDash } = render(<ResultDashboard onRetakeTest={jest.fn()} />);
      const retakeBtn = screen.getByRole('button', { name: /Initialize New Assessment Session/i });
      expect(retakeBtn.className).toContain('rounded-full');
      unmountDash();
    });
  });
});
