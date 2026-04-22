export interface Materia {
  nome: string;
  topicos: string[];
  peso?: number;
  quantidade_questoes?: number;
}

export interface Cargo {
  titulo: string;
  codigo_edital?: string;
  vagas_ac: number;
  vagas_cr: number;
  vagas_pcd: number;
  vagas_negros: number;
  vagas_indigenas: number;
  vagas_trans: number;
  vagas_total: number;
  salario: number;
  escolaridade: string;
  area: string;
  atribuicoes: string;
  requisitos: string;
  lotation_cities: string;
  jornada: string;
  status: string;
  price: number;
  materias?: Materia[];
}

export interface Edital {
  id?: string;
  title: string;
  orgao: string;
  banca: string;
  published_at: string;
  inscription_start: string;
  inscription_end: string;
  payment_deadline: string;
  fee: number;
  exam_cities: string;
  data_prova: string;
  link_edital?: string;
  status: string;
  cargos: Cargo[];
}

export interface SSELogEvent {
  type: "log";
  message: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
}

export interface SSEDataEvent {
  type: "data";
  payload: Cargo;
}

export interface SSEPingEvent {
  type: "ping";
}

export type SSEEvent = SSELogEvent | SSEDataEvent | SSEPingEvent;

export type ConnectionStatus = "connecting" | "connected" | "error" | "closed";

export type ProcessingStatus = "idle" | "processing" | "done" | "error";
