import React from 'react';

const Footer = () => {
  return (
    <footer className="py-8 bg-white text-center text-sm text-gray-500 border-t border-gray-200 mt-auto">
      <div className="container mx-auto px-4">
        <p>© {new Date().getFullYear()} Research Paper Proofreader. A helpful tool for researchers.</p>
      </div>
    </footer>
  );
};

export default Footer;
