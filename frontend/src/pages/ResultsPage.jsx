import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import ReactSpeedometer from 'react-d3-speedometer';
import axios from 'axios';

const API_BASE_URL = (
  import.meta.env.VITE_SERVER_URL || import.meta.env.VITE_BACKEND_URL || ''
).replace(/\/$/, '');

const ResultsPage = () => {
  const location = useLocation();
  const { results } = location.state || {};
  const [isGenerating, setIsGenerating] = useState(false);

  if (!results) {
    return (
      <div className="text-center p-8">
        <h1 className="text-2xl font-bold text-red-500">No results found.</h1>
        <p className="mt-2 text-gray-600">Please go back and upload a paper to see the analysis.</p>
      </div>
    );
  }

  const handleGenerateReport = async () => {
    setIsGenerating(true);
    try {
      if (!API_BASE_URL) {
        throw new Error('Backend URL is not configured. Set VITE_SERVER_URL (or VITE_BACKEND_URL).');
      }

      console.log('Downloading analysis report from:', `${API_BASE_URL}/api/generate-report`);
      
      const response = await axios.post(
        `${API_BASE_URL}/api/generate-report`, 
        { results }, 
        {
          responseType: 'blob',
          headers: { 'Content-Type': 'application/json' }
        }
      );
      
      console.log('Report generated successfully:', response.status);
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'analysis_report.pdf');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      console.log('PDF download initiated');
    } catch (err) {
      console.error('Failed to generate report:', err.response?.status, err.message);
      console.error('Error details:', err.response?.data);
      alert(`Failed to generate report: ${err.response?.data?.error || err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const { summary, issues } = results;

  const getSeverityClass = (severity) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 border-red-500 text-red-800';
      case 'warning':
        return 'bg-yellow-100 border-yellow-500 text-yellow-800';
      case 'info':
        return 'bg-blue-100 border-blue-500 text-blue-800';
      default:
        return 'bg-gray-100 border-gray-500 text-gray-800';
    }
  };

  return (
    <div className="container mx-auto p-8">
      <div className="bg-white p-6 rounded-lg shadow-lg mb-8 flex flex-col items-center text-center">
        <h2 className="text-3xl font-bold text-gray-800 mb-6">Analysis Complete</h2>
        
        <div className="h-48 w-75">
          <ReactSpeedometer
            value={summary.score || 0}
            minValue={0}
            maxValue={100}
            segments={5}
            segmentColors={["#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e"]}
            currentValueText="Score: ${value}"
            textColor="#333"
            needleColor="#1f2937"
            fontFamily="inherit"
          />
        </div>

        <div className="flex justify-center gap-8 mt-4 text-lg">
          <p><span className="font-bold text-red-600">{summary.critical}</span> Critical</p>
          <p><span className="font-bold text-yellow-600">{summary.warning}</span> Warnings</p>
          <p><span className="font-bold text-blue-600">{summary.info}</span> Info</p>
        </div>

        {/* Scoring Formula Breakdown */}
        <details className="mt-6 w-full border border-gray-300 rounded-lg p-4 group bg-gray-50 hover:bg-gray-100 transition-colors">
          <summary className="cursor-pointer font-semibold text-gray-800 flex justify-between items-center">
            <span className="flex items-center gap-2">
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              How is your score calculated?
            </span>
            <span className="transition group-open:rotate-180">
              <svg fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="24"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </summary>
          <div className="mt-4 space-y-4 text-left">
            <div className="bg-white p-4 rounded border-l-4 border-blue-500">
              <p className="text-sm font-mono text-gray-700 mb-3">
                <span className="font-bold text-lg">Score = 100 − (C × 2.5) − (log(1+W) × 2) − (log(1+I) × 0.5)</span>
              </p>
              <div className="text-sm text-gray-600 space-y-2">
                <p><span className="font-semibold">Where:</span></p>
                <p className="ml-4">• <span className="font-semibold text-red-600">C (Critical)</span> = {summary.critical}</p>
                <p className="ml-4">• <span className="font-semibold text-yellow-600">W (Warning)</span> = {summary.warning}</p>
                <p className="ml-4">• <span className="font-semibold text-blue-600">I (Info)</span> = {summary.info}</p>
                <p className="ml-4 mt-2 text-xs text-gray-500">log = natural logarithm (ln)</p>
              </div>
            </div>
            <div className="bg-white p-4 rounded border-l-4 border-green-500">
              <p className="text-sm text-gray-600"><span className="font-semibold">Calculation:</span></p>
              <p className="text-sm font-mono text-gray-700 mt-2">
                100 − ({summary.critical} × 2.5) − (log(1+{summary.warning}) × 2) − (log(1+{summary.info}) × 0.5)
              </p>
              <p className="text-sm font-mono text-gray-700 mt-2">
                = 100 − {(summary.critical * 2.5).toFixed(1)} − {(Math.log(1 + summary.warning) * 2).toFixed(2)} − {(Math.log(1 + summary.info) * 0.5).toFixed(2)}
              </p>
              <p className="text-sm font-bold text-green-600 mt-2">
                = <span className="text-lg">{summary.score}</span>
              </p>
            </div>
            <div className="text-xs text-gray-500 bg-gray-100 p-3 rounded">
              <p>💡 <span className="font-semibold">How it works:</span> Critical issues have direct linear penalty (2.5 per issue). Warnings and Info use logarithmic scaling, so papers with many issues are penalized fairly—150+ warnings score lower than 50-70 warnings, but without harsh cliffs.</p>
            </div>
          </div>
        </details>

        <button 
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className="mt-6 px-6 py-3 bg-[#e5322d] text-white font-bold rounded-lg shadow hover:bg-[#d62828] transition-colors disabled:opacity-50 flex gap-2 items-center"
        >
          {isGenerating ? 'Generating Report...' : 'Download Analysis Report'}
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Detailed Findings</h2>
        {Object.entries(issues).map(([category, issueList]) => {
          const hasCritical = issueList.some(issue => issue.severity === 'critical');
          return issueList.length > 0 && (
            <details key={category} className="mb-4 group border border-gray-200 rounded-lg">
              <summary className={`text-xl font-semibold capitalize p-4 cursor-pointer flex justify-between items-center group-open:border-b border-gray-200 transition-colors ${hasCritical ? 'bg-red-50 hover:bg-red-100' : 'bg-gray-50 hover:bg-gray-100'}`}>
                <span className={hasCritical ? 'text-red-700' : 'text-gray-800'}>{hasCritical && '⚠️ '}{category} Issues <span className={`text-sm py-1 px-2 rounded-full ml-2 ${hasCritical ? 'bg-red-200 text-red-700' : 'bg-gray-200 text-gray-700'}`}>{issueList.length}</span></span>
                <span className="transition group-open:rotate-180">
                  <svg fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="24"><polyline points="6 9 12 15 18 9"/></svg>
                </span>
              </summary>
              <div className="p-4 space-y-4 max-h-100 overflow-y-auto bg-white">
                {issueList.map((issue, index) => (
                  <div key={index} className={`p-4 border-l-4 rounded-r-lg ${getSeverityClass(issue.severity)}`}>
                    <p className="font-bold">{issue.message}</p>
                    {issue.snippet && <p className="mt-1 text-sm italic opacity-80">"{issue.snippet}"</p>}
                    {issue.suggestion && <p className="mt-1 text-sm"><span className="font-semibold">Suggestion:</span> {issue.suggestion}</p>}
                    {issue.page && <p className="text-xs mt-2 opacity-60">Page: {issue.page}</p>}
                  </div>
                ))}
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
};

export default ResultsPage;
