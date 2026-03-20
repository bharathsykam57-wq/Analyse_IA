"use client";

import { useState, useEffect } from "react";
import { fetchFiles, uploadFile, UploadedFile } from "@/features/upload/api/upload";
import { Dropzone } from "@/features/upload/components/Dropzone";
import { FileType, FileText, Trash2, CalendarDays, HardDrive, RefreshCcw, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

export default function UploadPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(true);
  
  const [uploadingCsv, setUploadingCsv] = useState(false);
  const [csvProgress, setCsvProgress] = useState(0);
  
  const [uploadingPdf, setUploadingPdf] = useState(false);
  const [pdfProgress, setPdfProgress] = useState(0);

  const loadFiles = async () => {
    try {
      setIsLoadingList(true);
      const data = await fetchFiles();
      setFiles(data);
    } catch (error) {
      console.error("Failed to load files", error);
    } finally {
      setIsLoadingList(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const handleFileUpload = async (file: File, type: 'csv' | 'pdf') => {
    const isCsv = type === 'csv';
    
    if (isCsv) {
      setUploadingCsv(true);
      setCsvProgress(0);
    } else {
      setUploadingPdf(true);
      setPdfProgress(0);
    }

    try {
      const newFile = await uploadFile(file, type, (progress) => {
        if (isCsv) {
          setCsvProgress(progress);
        } else {
          setPdfProgress(progress);
        }
      });
      // Append the new file locally since the mock backend list is static
      setFiles(prev => [newFile, ...prev]);
    } catch (error) {
      console.error("Upload failed", error);
      alert("Le téléversement a échoué. Veuillez réessayer.");
    } finally {
      // Simulate completing animation smoothly
      setTimeout(() => {
        if (isCsv) {
            setUploadingCsv(false);
            setCsvProgress(0);
          } else {
            setUploadingPdf(false);
            setPdfProgress(0);
          }
      }, 500);
    }
  };

  const handleDelete = (id: string) => {
    // Optimistic delete for UX
    setFiles(prev => prev.filter(f => f.file_id !== id));
    // Implementation for rigorous deletion would call the backend here
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-10">
      
      <div className="mb-10">
        <h1 className="text-3xl font-bold font-sans text-white mb-2 tracking-tight">Gestion des Données</h1>
        <p className="text-blue-300/60 leading-relaxed max-w-2xl mt-4">
          Téléversez vos jeux de données pour les analyser. Nous supportons les fichiers CSV (Analyse AutoML) et les documents PDF (Analyse RAG).
        </p>
      </div>

      {/* Upload Dropzones */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Dropzone 
          type="csv"
          accept=".csv,text/csv"
          maxSizeMB={50}
          onFileSelect={handleFileUpload}
          isUploading={uploadingCsv}
          progress={csvProgress}
        />
        <Dropzone 
          type="pdf"
          accept=".pdf,application/pdf"
          maxSizeMB={20}
          onFileSelect={handleFileUpload}
          isUploading={uploadingPdf}
          progress={pdfProgress}
        />
      </div>

      {/* Uploaded Files Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
        <div className="p-6 border-b border-border flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Fichiers récents</h2>
          <button 
            onClick={loadFiles} 
            disabled={isLoadingList}
            className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors disabled:opacity-50"
          >
            <RefreshCcw className={`w-4 h-4 ${isLoadingList ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-400">
            <thead className="text-xs uppercase bg-black/20 text-gray-500 border-b border-border">
              <tr>
                <th className="px-6 py-4 font-medium">Nom du Fichier</th>
                <th className="px-6 py-4 font-medium">Taille</th>
                <th className="px-6 py-4 font-medium">Date de téléversement</th>
                <th className="px-6 py-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoadingList && files.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
                    Chargement des fichiers...
                  </td>
                </tr>
              ) : files.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-gray-500">
                    Aucun fichier téléversé pour le moment.
                  </td>
                </tr>
              ) : (
                files.map((file) => {
                  const isPdf = file.type.includes('pdf') || file.filename.endsWith('.pdf');
                  return (
                    <tr key={file.file_id} className="border-b border-border/50 hover:bg-white/[0.02] transition-colors group">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${isPdf ? 'bg-red-500/10 text-red-500' : 'bg-emerald-500/10 text-emerald-500'}`}>
                            {isPdf ? <FileText className="w-4 h-4" /> : <FileType className="w-4 h-4" />}
                          </div>
                          <span className="font-medium text-gray-200 truncate max-w-[200px] md:max-w-xs" title={file.filename}>
                            {file.filename}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <HardDrive className="w-4 h-4 text-gray-500" />
                          {formatSize(file.size_bytes)}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <CalendarDays className="w-4 h-4 text-gray-500" />
                          {formatDistanceToNow(new Date(file.uploaded_at), { addSuffix: true, locale: fr })}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button 
                          onClick={() => handleDelete(file.file_id)}
                          className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                          title="Supprimer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
