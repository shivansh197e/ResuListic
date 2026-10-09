import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import UploadResume from '../components/UploadResume';
import Quiz from '../components/Quiz';
import ResultDashboard from '../components/ResultDashboard';

// Mock axios to test both success and failure paths
jest.mock('axios');
const axios = require('axios');

describe('Empirical Verification: Redesigned Frontend Components', () => {

  describe('UploadResume Component Verification', () => {
    beforeEach(() => {
      jest.clearAllMocks();
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    test('1. Validates drag-and-drop rejection of invalid file extensions', () => {
      render(<UploadResume userId="test_user" onUploadSuccess={jest.fn()} />);
      
      const dropZone = screen.getByLabelText(/upload resume file/i).parentElement;

      // Simulate dragging over
      fireEvent.dragOver(dropZone);
      expect(dropZone.className).toContain('border-sky-400');

      // Simulate dragging leave
      fireEvent.dragLeave(dropZone);
      expect(dropZone.className).not.toContain('border-sky-400');

      // Drop invalid file (.exe)
      const invalidFile = new File(['dummy content'], 'malicious.exe', { type: 'application/x-msdownload' });
      fireEvent.drop(dropZone, {
        dataTransfer: {
          files: [invalidFile]
        }
      });

      // Error message must appear
      expect(screen.getByText(/Please select a PDF or DOCX file first!/i)).toBeInTheDocument();
    });

    test('2. Validates drag-and-drop acceptance of valid PDF file', () => {
      render(<UploadResume userId="test_user" onUploadSuccess={jest.fn()} />);
      
      const dropZone = screen.getByLabelText(/upload resume file/i).parentElement;
      const validFile = new File(['valid pdf content'], 'my_resume.pdf', { type: 'application/pdf' });

      fireEvent.drop(dropZone, {
        dataTransfer: {
          files: [validFile]
        }
      });

      // Filename should be displayed
      expect(screen.getByText('my_resume.pdf')).toBeInTheDocument();
      expect(screen.getByText(/File ready for parsing/i)).toBeInTheDocument();

      // Change file button should appear
      const changeBtn = screen.getByRole('button', { name: /change file/i });
      expect(changeBtn).toBeInTheDocument();
      expect(changeBtn.className).toContain('rounded-full');

      // Clicking Change File resets file
      fireEvent.click(changeBtn);
      expect(screen.queryByText('my_resume.pdf')).not.toBeInTheDocument();
      expect(screen.getByText(/Click or drag your resume here/i)).toBeInTheDocument();
    });

    test('3. Validates submit button styling and upload error fallback flow', async () => {
      const mockSuccess = jest.fn();
      axios.post.mockRejectedValueOnce(new Error('Network error'));

      render(<UploadResume userId="test_user" onUploadSuccess={mockSuccess} />);
      
      const fileInput = screen.getByLabelText(/upload resume file/i);
      const validFile = new File(['content'], 'test_resume.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });

      fireEvent.change(fileInput, { target: { files: [validFile] } });

      const submitBtn = screen.getByRole('button', { name: /Upload & Parse Resume/i });
      // Button must be fully rounded
      expect(submitBtn.className).toContain('rounded-full');

      // Click submit
      fireEvent.click(submitBtn);

      // Verify network error handled and fallback timer triggers onUploadSuccess
      await waitFor(() => {
        expect(screen.getByText(/Upload failed. Make sure backend is running/i)).toBeInTheDocument();
      });

      act(() => {
        jest.advanceTimersByTime(1000);
      });

      expect(mockSuccess).toHaveBeenCalled();
    });
  });

  describe('Quiz Component Verification', () => {
    beforeEach(() => {
      jest.clearAllMocks();
    });

    test('1. Validates test initialization and start button styling', async () => {
      axios.post.mockRejectedValueOnce(new Error('Backend offline'));

      render(<Quiz userId="test_user" selectedSkills={['React', 'JavaScript']} />);

      expect(screen.getByText(/Dynamic AI Assessment/i)).toBeInTheDocument();
      expect(screen.getByText('React')).toBeInTheDocument();
      expect(screen.getByText('JavaScript')).toBeInTheDocument();

      const startBtn = screen.getByRole('button', { name: /Start Technical Evaluation/i });
      expect(startBtn.className).toContain('rounded-full');

      // Click start test
      await act(async () => {
        fireEvent.click(startBtn);
      });

      // Verify questions loaded via fallback mock
      expect(screen.getByText(/Which hook is used to manage state in a React functional component\?/i)).toBeInTheDocument();
      expect(screen.getByText(/Question 1 of 2/i)).toBeInTheDocument();
    });

    test('2. Validates radio button selection for MCQ and stepper navigation', async () => {
      axios.post.mockRejectedValueOnce(new Error('Backend offline'));

      render(<Quiz userId="test_user" selectedSkills={['React']} />);

      // Start test
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Start Technical Evaluation/i }));
      });

      // Check Previous button is disabled on question 1
      const prevBtn = screen.getByRole('button', { name: /Previous/i });
      expect(prevBtn).toBeDisabled();
      expect(prevBtn.className).toContain('rounded-full');

      // Check MCQ radio buttons
      const options = ['useEffect()', 'useState()', 'useContext()', 'useReducer()'];
      options.forEach(opt => {
        expect(screen.getByText(opt)).toBeInTheDocument();
      });

      const useStateRadio = screen.getByDisplayValue('useState()');
      expect(useStateRadio.checked).toBe(false);

      // Select useState()
      fireEvent.click(useStateRadio);
      expect(useStateRadio.checked).toBe(true);

      // Stepper Next button
      const nextBtn = screen.getByRole('button', { name: /Next/i });
      expect(nextBtn.className).toContain('rounded-full');

      // Navigate to Next question
      fireEvent.click(nextBtn);

      // Question 2 is coding
      expect(screen.getByText(/Write an optimized JavaScript function to reverse a string/i)).toBeInTheDocument();
      expect(screen.getByText(/Question 2 of 2/i)).toBeInTheDocument();

      // Previous button should now be enabled
      expect(prevBtn).not.toBeDisabled();

      // Navigate back to Previous question and verify selected state is preserved
      fireEvent.click(prevBtn);
      expect(screen.getByDisplayValue('useState()').checked).toBe(true);
    });

    test('3. Validates coding textarea input and test submission handshake', async () => {
      axios.post.mockRejectedValueOnce(new Error('Backend offline'));

      render(<Quiz userId="test_user" selectedSkills={['React']} />);

      // Start test
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Start Technical Evaluation/i }));
      });

      // Go to Question 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      // Find textarea
      const textarea = screen.getByPlaceholderText(/\/\/ Write your optimized solution here\.\.\./i);
      expect(textarea).toBeInTheDocument();

      // Enter code
      const sampleCode = 'function reverseString(s) { return s.split("").reverse().join(""); }';
      fireEvent.change(textarea, { target: { value: sampleCode } });
      expect(textarea.value).toBe(sampleCode);

      // Submit button should appear on the last question
      const submitBtn = screen.getByRole('button', { name: /Submit Test/i });
      expect(submitBtn.className).toContain('rounded-full');

      // Submit the test
      fireEvent.click(submitBtn);

      // Dashboard should now be rendered
      expect(screen.getByText(/Performance Intelligence Dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/94%/i)).toBeInTheDocument();
      expect(screen.getByText(/S\+/i)).toBeInTheDocument();

      // Retake button should be present and fully rounded
      const retakeBtn = screen.getByRole('button', { name: /Initialize New Assessment Session/i });
      expect(retakeBtn).toBeInTheDocument();
      expect(retakeBtn.className).toContain('rounded-full');

      // Clicking retake button resets back to Quiz initial screen
      fireEvent.click(retakeBtn);
      expect(screen.getByText(/Start Technical Evaluation/i)).toBeInTheDocument();
    });
  });

  describe('ResultDashboard Component Verification', () => {
    test('1. Validates custom results rendering, badges, and progress meters', () => {
      const customResults = {
        score_percentage: 88,
        correct_answers: 4,
        total_questions: 5,
        grade: 'A',
        ai_feedback: 'Solid foundational and algorithmic competency demonstrated.',
        skill_breakdown: [
          { skill: 'Data Structures', status: 'Proficient', percentage: 85 },
          { skill: 'React Architecture', status: 'Advanced', percentage: 90 }
        ]
      };

      const mockRetake = jest.fn();
      render(<ResultDashboard results={customResults} onRetakeTest={mockRetake} />);

      expect(screen.getByText('88%')).toBeInTheDocument();
      expect(screen.getByText('A')).toBeInTheDocument();
      expect(screen.getByText('4/5')).toBeInTheDocument();
      expect(screen.getByText('"Solid foundational and algorithmic competency demonstrated."')).toBeInTheDocument();
      expect(screen.getByText('Data Structures')).toBeInTheDocument();
      expect(screen.getByText('React Architecture')).toBeInTheDocument();
      expect(screen.getByText('85%')).toBeInTheDocument();
      expect(screen.getByText('90%')).toBeInTheDocument();

      const retakeBtn = screen.getByRole('button', { name: /Initialize New Assessment Session/i });
      expect(retakeBtn.className).toContain('rounded-full');

      fireEvent.click(retakeBtn);
      expect(mockRetake).toHaveBeenCalledTimes(1);
    });

    test('2. Validates default fallback results when results prop is null', () => {
      render(<ResultDashboard results={null} onRetakeTest={jest.fn()} />);

      expect(screen.getByText('94%')).toBeInTheDocument();
      expect(screen.getByText('S+')).toBeInTheDocument();
      expect(screen.getByText('5/5')).toBeInTheDocument();
      expect(screen.getByText(/Exceptional mastery demonstrated/i)).toBeInTheDocument();
      expect(screen.getByText('React Ecosystem & Hooks')).toBeInTheDocument();
    });
  });

  describe('CSS Styling Conformance Verification', () => {
    test('1. Validates rounded-full class on all primary action buttons', () => {
      const { unmount } = render(<UploadResume userId="test" onUploadSuccess={jest.fn()} />);
      const uploadButtons = screen.getAllByRole('button');
      uploadButtons.forEach(btn => {
        expect(btn.className).toContain('rounded-full');
      });
      unmount();

      render(<ResultDashboard onRetakeTest={jest.fn()} />);
      const resultButtons = screen.getAllByRole('button');
      resultButtons.forEach(btn => {
        expect(btn.className).toContain('rounded-full');
      });
    });
  });
});
