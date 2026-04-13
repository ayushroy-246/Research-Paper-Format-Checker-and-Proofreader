import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import ReactSpeedometer from 'react-d3-speedometer';
import axios from 'axios';

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
      const response = await axios.post(`${import.meta.env.VITE_SERVER_URL}/api/generate-report`, { results }, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'analysis_report.pdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Failed to generate report:', err);
      alert('Failed to generate report.');
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
        
        <div className="h-48 w-[300px]">
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

        <button 
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className="mt-6 px-6 py-3 bg-[#e5322d] text-white font-bold rounded-lg shadow hover:bg-[#d62828] transition-colors disabled:opacity-50 flex gap-2 items-center"
        >
          {isGenerating ? 'Generating...' : 'Download Full Report'}
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Detailed Findings</h2>
        {Object.entries(issues).map(([category, issueList]) =>
          issueList.length > 0 && (
            <details key={category} className="mb-4 group border border-gray-200 rounded-lg">
              <summary className="text-xl font-semibold capitalize p-4 cursor-pointer bg-gray-50 flex justify-between items-center group-open:border-b border-gray-200 hover:bg-gray-100 transition-colors">
                <span className="text-gray-800">{category} Issues <span className="bg-gray-200 text-gray-700 text-sm py-1 px-2 rounded-full ml-2">{issueList.length}</span></span>
                <span className="transition group-open:rotate-180">
                  <svg fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="24"><polyline points="6 9 12 15 18 9"/></svg>
                </span>
              </summary>
              <div className="p-4 space-y-4 max-h-[400px] overflow-y-auto bg-white">
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
          )
        )}
      </div>
    </div>
  );
};

export default ResultsPage;
