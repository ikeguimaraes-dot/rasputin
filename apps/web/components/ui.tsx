"use client";
import { X, FileSearch, LoaderCircle, TriangleAlert } from "lucide-react";
export function Button({
  children,
  secondary = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { secondary?: boolean }) {
  return (
    <button
      {...props}
      className={`button ${secondary ? "secondary" : ""} ${props.className || ""}`}
    >
      {children}
    </button>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: React.ReactNode;
  error?: boolean;
}) {
  return (
    <div
      role={error ? "alert" : "note"}
      className={`notice ${error ? "error" : ""}`}
    >
      <TriangleAlert />
      <div>{children}</div>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={20} />
      Carregando…
    </div>
  );
}
export function Status({ value }: { value: string }) {
  const labels: Record<string, string> = {
    concluida: "Concluída",
    processado: "Processado",
    enviado: "Na fila",
    pendente: "Na fila",
    executando: "Processando",
    erro: "Erro",
    proposta: "Proposta",
    aprovada: "Aprovada",
    rejeitada: "Rejeitada",
    revisar: "Revisar",
    risco: "Risco",
    alerta: "Alerta",
  };
  return <span className={`status ${value}`}>{labels[value] || value}</span>;
}
export function Empty({
  title,
  text,
  children,
}: {
  title: string;
  text: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <FileSearch size={22} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {children}
    </div>
  );
}
export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`modal ${wide ? "wide" : ""}`}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button
            className="button ghost"
            aria-label="Fechar"
            onClick={onClose}
          >
            <X />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </section>
    </div>
  );
}
