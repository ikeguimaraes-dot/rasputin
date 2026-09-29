"use client";
import {
  ArrowUpRight,
  Check,
  FileCheck2,
  UploadCloud,
  Building2,
  ArrowRight,
} from "lucide-react";
import type { Analysis, Client, Upload } from "@/lib/types";
import { formatDate } from "@/lib/client";
import { Button } from "./ui";
import { ReviewChart } from "./review-chart";

export function WorkspaceOverview({
  client,
  uploads,
  latest,
  onUpload,
  onClient,
  onAnalysis,
  onOpen,
}: {
  client?: Client;
  uploads: Upload[];
  latest?: Analysis;
  onUpload: () => void;
  onClient: () => void;
  onAnalysis: () => void;
  onOpen: () => void;
}) {
  const base = latest?.resumo?.base_review;
  const processed = uploads.some((u) => u.status === "processado");
  return (
    <>
      <section className="workspace-hero">
        <div className="hero-copy">
          <span className="hero-kicker">
            <span /> SEU OLHAR EXTRA NA CONFERÊNCIA
          </span>
          <h2>
            Mais clareza.
            <br />
            <em>Menos dúvidas.</em>
          </h2>
          <p>
            Da planilha ao relatório: encontre diferenças verificáveis, entenda
            cada valor e compartilhe uma conclusão clara com seu cliente.
          </p>
          <div className="hero-actions">
            <Button
              className="lime"
              onClick={latest ? onOpen : client ? onUpload : onClient}
            >
              {latest ? <FileCheck2 /> : <UploadCloud />}
              {latest
                ? "Abrir última conferência"
                : client
                  ? "Enviar primeiro arquivo"
                  : "Começar com um cliente"}
              <ArrowUpRight />
            </Button>
            <span>Rastreável. Organizado. Simples.</span>
          </div>
        </div>
        <div className="mascot-stage">
          <div className="mascot-orbit" />
          <img
            src="/brand/rasputin-mascot.png"
            alt="Mascote Rasputin, criatura verde com dois olhos atentos"
            width="1024"
            height="1536"
            fetchPriority="high"
          />
          <span className="mascot-caption">
            <span /> De olho nos detalhes.
          </span>
        </div>
      </section>
      <nav className="workflow" aria-label="Etapas da conferência">
        {[
          {
            title: "Cliente",
            detail: client ? "Perfil cadastrado" : "Cadastre o estabelecimento",
            done: !!client,
            icon: Building2,
            click: onClient,
            disabled: false,
          },
          {
            title: "Documentos",
            detail: processed
              ? "Arquivo pronto para análise"
              : "Envie a planilha ou XML",
            done: processed,
            icon: UploadCloud,
            click: onUpload,
            disabled: !client,
          },
          {
            title: "Conferência",
            detail: latest
              ? "Resultado disponível"
              : "Escolha o período e analise",
            done: !!latest,
            icon: FileCheck2,
            click: onAnalysis,
            disabled: !processed,
          },
          {
            title: "Relatório",
            detail: "Revise e exporte para o cliente",
            done: false,
            icon: ArrowUpRight,
            click: onOpen,
            disabled: !latest,
          },
        ].map((step, i) => (
          <button
            key={step.title}
            disabled={step.disabled}
            onClick={step.click}
            className={`workflow-step ${step.done ? "complete" : ""}`}
          >
            <span className="workflow-number">
              {step.done ? <Check size={16} /> : `0${i + 1}`}
            </span>
            <span>
              <strong>{step.title}</strong>
              <small>{step.detail}</small>
            </span>
            <ArrowRight className="step-arrow" />
          </button>
        ))}
      </nav>
      {latest && (
        <section className="overview-insight card">
          <div className="insight-copy">
            <span className="eyebrow">ÚLTIMA CONFERÊNCIA</span>
            <h2>
              O que merece
              <br />a sua atenção.
            </h2>
            <p>
              {formatDate(latest.periodo_ini)} a{" "}
              {formatDate(latest.periodo_fim)}
            </p>
            <strong className="insight-number">
              {latest.resumo?.findings ?? "—"}
              <span>linhas com divergência documental</span>
            </strong>
            <button className="text-link" onClick={onOpen}>
              Explorar o relatório <ArrowUpRight size={17} />
            </button>
          </div>
          {base ? (
            <ReviewChart base={base} compact />
          ) : (
            <div className="insight-empty">
              <FileCheck2 size={36} />
              <h3>Os detalhes estão no relatório</h3>
              <p>
                Abra a conferência para consultar as evidências de cada
                apontamento.
              </p>
            </div>
          )}
        </section>
      )}
    </>
  );
}
