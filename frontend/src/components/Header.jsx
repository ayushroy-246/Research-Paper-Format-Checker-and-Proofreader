import React from 'react';
import { Link } from 'react-router-dom';

const Header = () => {
  return (
    <header className="h-17.5 bg-white shadow-sm flex items-center px-6 lg:px-12 sticky top-0 z-50">
      
      <Link
        to="/"
        className="group flex items-center gap-2 text-2xl font-black text-[#333] hover:text-[#e5322d] transition-all duration-300"
      >
        
        <svg
          className="w-8 h-8 text-[#e5322d] transition-transform duration-300 group-hover:scale-105"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          {/* Top Layer (moves DOWN to middle) */}
          <path
            d="M12 2L2 7l10 5 10-5-10-5z"
            className="transition-all duration-300 ease-in-out 
                       group-hover:translate-y-1.75"
          />

          {/* Middle Layer (stays same) */}
          <path
            d="M12 9l-10 5 10 5 10-5-10-5z"
            className="transition-all duration-300 ease-in-out"
          />

          {/* Bottom Layer (moves UP to middle) */}
          <path
            d="M12 16l-10 5 10 5 10-5-10-5z"
            className="transition-all duration-300 ease-in-out 
                       group-hover:-translate-y-1.75"
          />
        </svg>

        <span className="tracking-tight">
          Paper<span className="text-[#e5322d]">Proof</span>
        </span>
      </Link>

    </header>
  );
};

export default Header;