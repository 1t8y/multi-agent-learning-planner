import { ReactNode } from 'react';

interface ResultCardProps {
  title: string;
  icon: ReactNode;
  color: string;
  children: ReactNode;
}

export function ResultCard({ title, icon, color, children }: ResultCardProps) {
  return (
    <div className="bg-white/10 backdrop-blur-sm rounded-lg shadow-lg overflow-hidden">
      <div className={`${color} px-4 py-3 flex items-center gap-2`}>
        {icon}
        <h3 className="text-lg font-semibold text-white">{title}</h3>
      </div>
      <div className="p-4 text-white/90">
        {children}
      </div>
    </div>
  );
}
