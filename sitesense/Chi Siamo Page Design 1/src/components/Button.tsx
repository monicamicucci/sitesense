interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'light';
  children: React.ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
}

export function Button({ variant = 'primary', children, onClick, type = 'button' }: ButtonProps) {
  const baseClasses = "px-8 py-4 rounded-lg transition-all duration-300 text-lg font-medium";
  
  const variantClasses = {
    primary: "bg-[#004D43] text-white hover:bg-[#003830]",
    secondary: "bg-transparent border-2 border-[#004D43] text-[#004D43] hover:bg-[#004D43] hover:text-white",
    light: "bg-white text-[#004D43] hover:bg-gray-100"
  };

  return (
    <button 
      type={type}
      onClick={onClick}
      className={`${baseClasses} ${variantClasses[variant]}`}
    >
      {children}
    </button>
  );
}
