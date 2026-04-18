import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import axios from 'axios';

const FileUpload = () => {
  const [file, setFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const { register, watch, reset } = useForm({
    defaultValues: {
      standard: 'IEEE',
      paper_type: '',
      review_mode: '',
      use_crossref: false,
    },
  });

  const standard = watch('standard');
  const paper_type = watch('paper_type');
  const review_mode = watch('review_mode');
  const use_crossref = watch('use_crossref');

  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
  });

  const handleUpload = async () => {
    if (!file) return;

    setIsLoading(true);
    setError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      // Step 1: Upload
      const uploadResponse = await axios.post(`${import.meta.env.VITE_SERVER_URL}/api/upload`, formData);
      console.log('Upload successful:', uploadResponse.data);

      // Step 2: Analyze
      const analyzeData = {
        standard,
        paper_type: paper_type || null,
        review_mode: review_mode || null,
        use_crossref,
      };
      const analyzeResponse = await axios.post(`${import.meta.env.VITE_SERVER_URL}/api/analyze`, analyzeData);
      console.log('Analysis successful:', analyzeResponse.data);

      // Navigate to results page with data
      navigate('/results', { state: { results: analyzeResponse.data } });

    } catch (err) {
      console.error('An error occurred:', err);
      setError(err.response?.data?.error || 'An error occurred during analysis');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    setError(null);
  };

  return (
    <div className="w-full max-w-5xl mx-auto">
      {!file ? (
        <div className="flex justify-center w-full">
          <div
            {...getRootProps()}
            className={`w-200 h-87.5 flex items-center justify-center rounded-[10px] text-center cursor-pointer transition-all duration-300 shadow-[0_10px_40px_rgba(0,0,0,0.08)] ${
              isDragActive ? 'bg-[#ffeb00] scale-[1.02]' : 'bg-[#e5322d] hover:bg-[#d62828]'
            }`}
          >
            <input {...getInputProps()} />
            <div className="text-white flex flex-col items-center">
              <svg className="w-20 h-20 mb-6 opacity-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <button className="text-[28px] font-bold tracking-wide">
                {isDragActive ? "Drop PDF successfully" : "Select PDF file"}
              </button>
              <p className="mt-4 text-[17px] opacity-80 font-medium">
                or drop PDF document here
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row shadow-[0_10px_40px_rgba(0,0,0,0.08)] rounded-[10px] bg-[#fbfbfb] overflow-hidden">
          {/* Left Side: Document Preview Area */}
          <div className="lg:w-2/3 bg-[#f0f0f0] p-10 flex flex-col items-center justify-center relative min-h-100">
            {/* Simple File Card */}
            <div className="bg-white p-6 shadow-sm rounded-lg flex flex-col items-center w-55 aspect-[1/1.4] justify-center mx-auto border border-gray-200 relative group cursor-pointer">
              <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={handleRemoveFile} className="bg-red-500 text-white rounded-full p-1.5 hover:bg-red-600 shadow-md">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <svg className="w-16 h-16 text-red-500 mb-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
              </svg>
              <p className="text-sm font-bold text-gray-800 text-center break-all w-full leading-tight line-clamp-3">{file.name}</p>
              <p className="text-xs text-gray-500 mt-2">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
            
            <button 
              onClick={handleRemoveFile} 
              className="mt-8 text-gray-500 hover:text-gray-800 font-semibold text-sm underline decoration-2 underline-offset-4"
            >
              Select a different file
            </button>
          </div>

          {/* Right Side: Options Panel */}
          <div className="lg:w-1/3 bg-white p-8 lg:p-10 border-l border-gray-200 flex flex-col justify-between relative">
            
            {/* Loading Overlay */}
            {isLoading && (
              <div className="absolute inset-0 bg-white/80 z-10 flex flex-col items-center justify-center rounded-lg backdrop-blur-sm">
                <div className="w-16 h-16 border-4 border-gray-200 border-t-[#e5322d] rounded-full animate-spin"></div>
                <p className="mt-4 text-gray-800 font-semibold text-lg">Analyzing Document...</p>
                <p className="mt-2 text-gray-500 text-sm">Please wait</p>
              </div>
            )}

            <div>
              <h3 className="text-2xl font-bold text-gray-800 mb-6">Analysis Options</h3>

              {error && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm font-medium">
                  ⚠️ {error}
                </div>
              )}

              <div className="space-y-6">
                {/* Standard Dropdown */}
                <div className="relative">
                  <label className="block text-[13px] font-bold text-gray-800 uppercase tracking-wider mb-2">
                    Citation Standard
                  </label>
                  <div className="relative">
                    <select
                      {...register('standard')}
                      className="w-full p-4 text-[15px] font-semibold text-gray-700 bg-[#f7f7f9] border border-transparent rounded-lg focus:outline-none focus:ring-2 focus:ring-[#e5322d] focus:bg-white transition-all appearance-none cursor-pointer pr-10"
                    >
                      <option value="IEEE">IEEE — Conferences & Journals</option>
                      <option value="SPRINGER">Springer — LNCS / Journals</option>
                      <option value="ELSEVIER">Elsevier — Journals</option>
                      <option value="ACL">ACL — NLP Conferences</option>
                      <option value="CVPR">CVPR — Computer Vision</option>
                      <option value="NeurIPS">NeurIPS — Machine Learning</option>
                      <option value="ICML">ICML — Machine Learning</option>
                      <option value="AAAI">AAAI — AI</option>
                    </select>
                    <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-700 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
                  </div>
                </div>

                {/* Paper Type */}
                <div className="relative">
                  <label className="block text-[13px] font-bold text-gray-800 uppercase tracking-wider mb-2">
                    Submit Type (Optional)
                  </label>
                  <div className="relative">
                    <select
                      {...register('paper_type')}
                      className="w-full p-4 text-[15px] font-medium text-gray-600 bg-[#f7f7f9] border border-transparent rounded-lg focus:outline-none focus:ring-2 focus:ring-[#e5322d] focus:bg-white transition-all appearance-none cursor-pointer pr-10"
                    >
                      <option value="">Auto-Detect</option>
                      <option value="conference_submission">Conference Submission</option>
                      <option value="journal">Journal</option>
                      <option value="arxiv">arXiv Preprint</option>
                    </select>
                    <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
                  </div>
                </div>

                {/* Review Mode Dropdown */}
                <div className="relative">
                  <label className="block text-[13px] font-bold text-gray-800 uppercase tracking-wider mb-2">
                     Review Mode (Optional)
                  </label>
                  <div className="relative">
                    <select
                      {...register('review_mode')}
                      className="w-full p-4 text-[15px] font-medium text-gray-600 bg-[#f7f7f9] border border-transparent rounded-lg focus:outline-none focus:ring-2 focus:ring-[#e5322d] focus:bg-white transition-all appearance-none cursor-pointer pr-10"
                    >
                      <option value="">Auto-Detect</option>
                      <option value="blind">Blind Review</option>
                      <option value="camera_ready">Camera Ready</option>
                      <option value="published">Published</option>
                    </select>
                    <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
                  </div>
                </div>

                {/* Crossref Checkbox */}
                <label className="flex items-center cursor-pointer group mt-2">
                  <div className="relative flex items-center justify-center">
                    <input
                      type="checkbox"
                      {...register('use_crossref')}
                      className="w-6 h-6 rounded border-2 border-gray-300 text-[#e5322d] cursor-pointer focus:ring-[#e5322d] transition-all bg-[#f7f7f9]"
                    />
                  </div>
                  <span className="ml-3 text-[15px] font-bold text-gray-800 group-hover:text-[#e5322d] transition-colors">
                    Verify Citations against Crossref Database
                  </span>
                </label>
              </div>
            </div>

            {/* Action Button */}
            <div className="mt-8">
               <button
                onClick={handleUpload}
                className="w-full py-5.5 bg-[#e5322d] text-white text-xl font-bold tracking-wide rounded-lg shadow-lg hover:bg-[#d62828] hover:-translate-y-1 transition-all flex items-center justify-center gap-3"
              >
                Analyze Paper
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
