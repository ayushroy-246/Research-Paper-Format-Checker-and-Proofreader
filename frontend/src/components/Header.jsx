import React from 'react';
import { Link } from 'react-router-dom';

const Header = () => {
  return (
    <header className="h-[70px] bg-white shadow-sm flex items-center px-6 lg:px-12 sticky top-0 z-50">
      <Link to="/" className="flex items-center gap-2 text-2xl font-black text-[#333] hover:text-[#e5322d] transition-colors">
        <svg className="w-8 h-8 text-[#e5322d]" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 2L2 7l10 5 10-5-10-5zm0 7l-10 5 10 5 10-5-10-5zm0 7l-10 5 10 5 10-5-10-5z" />
        </svg>
        <span className="tracking-tight">Paper<span className="text-[#e5322d]">Proof</span></span>
      </Link>
    </header>
  );
};

export default Header;
