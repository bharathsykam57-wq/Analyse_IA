"use client";

import { useState, useCallback } from "react";
import { UploadCloud, FileType, FileText, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/shared/lib/utils";

interface DropzoneProps {
  accept: string;
  maxSizeMB: number;
  type: 'csv' | 'pdf';
  onFileSelect: (file: File, type: 'csv' | 'pdf') => void;
  isUploading: boolean;
  progress: number;
}

export function Dropzone({ accept, maxSizeMB, type, onFileSelect, isUploading, progress }: DropzoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isUploading) setIsDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    setError(null);

    if (isUploading) return;

    const files = Array.from(e.dataTransfer.files);
    processFiles(files);
  }, [isUploading]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    if (e.target.files?.length) {
      processFiles(Array.from(e.target.files));
    }
  };

  const processFiles = (files: File[]) => {
    if (files.length === 0) return;
    const file = files[0];
    
    // Validate Extension
    const isPDF = file.name.toLowerCase().endsWith('.pdf');
    const isCSV = file.name.toLowerCase().endsWith('.csv');
    
    if (type === 'pdf' && !isPDF) {
      setError("Veuillez déposer un fichier PDF.");
      return;
    }
    if (type === 'csv' && !isCSV) {
      setError("Veuillez déposer un fichier CSV.");
      return;
    }

    // Validate Size
    if (file.size > maxSizeMB * 1024 * 1024) {
      setError(`La taille du fichier dépasse la limite de ${maxSizeMB}MB.`);
      return;
    }

    onFileSelect(file, type);
  };

  const isPDF = type === 'pdf';

  return (
    <div
      onDragEnter={handleDragEnter}
      onDragOver={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "relative rounded-xl border-2 border-dashed p-8 transition-all duration-200 flex flex-col items-center justify-center text-center overflow-hidden",
        isDragActive 
          ? "border-primary bg-primary/10 shadow-[0_0_20px_rgba(37,99,235,0.2)]" 
          : "border-border bg-card hover:border-primary/50 hover:bg-card/80",
        isUploading && "pointer-events-none opacity-80"
      )}
    >
      {/* Upload Progress Overlay */}
      {isUploading && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
          <Loader2 className="w-10 h-10 text-primary animate-spin mb-4" />
          <p className="text-white font-medium mb-2">Téléversement en cours...</p>
          <div className="w-48 h-2 bg-gray-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-blue-300 mt-2">{progress}%</p>
        </div>
      )}

      <div className={cn(
        "w-16 h-16 rounded-full flex items-center justify-center mb-4 transition-transform",
        isDragActive && "scale-110",
        isPDF ? "bg-red-500/10 text-red-400" : "bg-emerald-500/10 text-emerald-400"
      )}>
        {isPDF ? <FileText className="w-8 h-8" /> : <FileType className="w-8 h-8" />}
      </div>
      
      <h3 className="text-lg font-semibold text-white mb-2">
        {isPDF ? "Déposer vos documents PDF" : "Déposer vos Datasets CSV"}
      </h3>
      <p className="text-sm text-gray-400 max-w-xs mb-6 leading-relaxed">
        Glissez-déposez votre fichier ici, ou cliquez pour parcourir.
        <br />
        <span className="text-xs font-medium text-gray-500 mt-1 inline-block">
           Limite: {maxSizeMB} MB
        </span>
      </p>

      {error ? (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 px-3 py-2 rounded-lg mb-6">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      ) : null}

      <label className={cn(
        "cursor-pointer px-6 py-2.5 rounded-lg text-sm font-medium transition-colors",
        isPDF 
          ? "bg-red-500/20 text-red-300 hover:bg-red-500/30" 
          : "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
      )}>
        Parcourir les fichiers
        <input
          type="file"
          className="hidden"
          accept={accept}
          onChange={handleFileInput}
          disabled={isUploading}
        />
      </label>
    </div>
  );
}
