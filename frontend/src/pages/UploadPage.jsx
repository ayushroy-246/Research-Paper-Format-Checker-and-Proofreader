import React from 'react';
import FileUpload from '../components/FileUpload';

const UploadPage = () => {
  return (
    <div className="flex-1 w-full flex flex-col items-center pt-16 pb-12 px-4">
      <div className="w-full max-w-4xl text-center mb-10">
        <h1 className="text-[40px] md:text-[52px] font-black text-[#333] leading-tight tracking-tight mb-4">
          Check Research Paper Format
        </h1>
        <p className="text-xl md:text-2xl text-[#47474f] font-normal">
          Make your IEEE, Springer, or Elsevier paper error-free by checking formatting, grammar, and citations.
        </p>
      </div>
      
      <FileUpload />
    </div>
  );
};

export default UploadPage;
