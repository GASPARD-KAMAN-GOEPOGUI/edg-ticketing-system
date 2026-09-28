export type Role =
  | "public"
  | "user"
  | "chief-service"
  | "technicien"
  | "chef-division-support"
  | "admin";

// "qualified", "pending" et "escalated" supprimés le 2026-09-28 : aucun ticket
// ne les portait et plus aucune transition n'y menait.
export type RequestStatus =
  | "new"
  | "qualifying"
  | "assigned"
  | "in_progress"
  | "resolved"
  | "closed"
  | "reopened"
  | "rejected"
  | "cancelled";

export const statusOrder: RequestStatus[] = [
  "new",
  "qualifying",
  "assigned",
  "in_progress",
  "resolved",
  "closed",
  "reopened",
  "rejected",
];

export type Priority = "low" | "medium" | "high" | "critical";

export type Direction = {
  id: string;
  name: string;
  services: { id: string; name: string }[];
};

export const directions: Direction[] = [
  {
    id: "dsi",
    name: "Direction des Systèmes d'Information",
    services: [
      { id: "dsi-support", name: "Support utilisateurs" },
      { id: "dsi-infra", name: "Infrastructure" },
      { id: "dsi-app", name: "Applications métier" },
    ],
  },
  {
    id: "com",
    name: "Direction Commerciale",
    services: [
      { id: "com-clients", name: "Service Clients" },
      { id: "com-fact", name: "Facturation" },
    ],
  },
  {
    id: "tech",
    name: "Direction Technique",
    services: [
      { id: "tech-maint", name: "Maintenance" },
      { id: "tech-trav", name: "Travaux" },
    ],
  },
  {
    id: "reseau",
    name: "Direction Réseau",
    services: [
      { id: "res-ht", name: "Haute tension" },
      { id: "res-bt", name: "Basse tension" },
      { id: "res-pannes", name: "Cellule pannes" },
    ],
  },
  {
    id: "rh",
    name: "Direction Ressources Humaines",
    services: [
      { id: "rh-paie", name: "Paie" },
      { id: "rh-carrieres", name: "Carrières" },
    ],
  },
  {
    id: "fin",
    name: "Direction Financière",
    services: [
      { id: "fin-compta", name: "Comptabilité" },
      { id: "fin-budget", name: "Budget" },
    ],
  },
  {
    id: "comm",
    name: "Direction Communication",
    services: [{ id: "comm-presse", name: "Relations presse" }],
  },
  {
    id: "dg",
    name: "Direction Générale",
    services: [{ id: "dg-cab", name: "Cabinet" }],
  },
];

export type AppUser = {
  id: string;
  name: string;
  email: string;
  role: Role;
  direction?: string;
  service?: string;
  avatar?: string;
  matricule?: string;
  job?: string;
};

export const users: AppUser[] = [
  { id: "u1", name: "Mariama Diallo", email: "mariama@edg.gn", role: "user", matricule: "EDG-2847", job: "Technicienne", direction: "dsi", service: "dsi-app" },
  { id: "u2", name: "Ousmane Camara", email: "ousmane@edg.gn", role: "chief-service", direction: "dsi", service: "dsi-support", matricule: "EDG-1023", job: "Chef de service" },
  { id: "u3", name: "Fatoumata Bah", email: "fatoumata@edg.gn", role: "chief-service", direction: "dsi", service: "dsi-support", matricule: "EDG-0541", job: "Chef service support" },
  { id: "u4", name: "Ibrahima Sow", email: "ibrahima@edg.gn", role: "chief-service", direction: "dsi", matricule: "EDG-0102", job: "Directeur DSI" },
  { id: "u5", name: "Aïssatou Barry", email: "aissatou@edg.gn", role: "chief-service", direction: "dg", matricule: "EDG-0001", job: "Directrice" },
  { id: "u6", name: "Mohamed Touré", email: "admin@edg.gn", role: "admin", matricule: "EDG-9999", job: "Administrateur système" },
  { id: "u7", name: "Sékou Condé", email: "sekou@edg.gn", role: "chief-service", direction: "reseau", service: "res-pannes", matricule: "EDG-3312", job: "Agent terrain réseau" },
  { id: "u8", name: "Hadja Sylla", email: "hadja@edg.gn", role: "chief-service", direction: "com", service: "com-clients", matricule: "EDG-2204", job: "Chargée clientèle" },
  { id: "u9", name: "Alpha Diaby", email: "alpha.diaby@gmail.com", role: "user" },
  { id: "u10", name: "Kadiatou Keita", email: "kadi@yahoo.com", role: "user" },
  /* Technique */
  { id: "u11", name: "Mamadou Barry", email: "mamadou.barry@edg.gn", role: "chief-service", direction: "tech", service: "tech-maint" },
  { id: "u12", name: "Mariame Kouyaté", email: "mariame@edg.gn", role: "chief-service", direction: "tech", service: "tech-maint" },
  { id: "u13", name: "Boubacar Diallo", email: "boubacar@edg.gn", role: "chief-service", direction: "tech" },
  /* Financière */
  { id: "u14", name: "Hawa Cissé", email: "hawa@edg.gn", role: "chief-service", direction: "fin", service: "fin-compta" },
  { id: "u15", name: "Lansana Traoré", email: "lansana@edg.gn", role: "chief-service", direction: "fin", service: "fin-budget" },
  { id: "u16", name: "Ibrahima Bah", email: "ibrahima.bah@edg.gn", role: "chief-service", direction: "fin" },
  /* RH */
  { id: "u17", name: "Nènè Camara", email: "nene@edg.gn", role: "chief-service", direction: "rh", service: "rh-carrieres" },
  { id: "u18", name: "Fatoumata Konaté", email: "fatou.konate@edg.gn", role: "chief-service", direction: "rh", service: "rh-paie" },
  { id: "u19", name: "Alpha Touré", email: "alpha.toure@edg.gn", role: "chief-service", direction: "rh" },
  /* Réseau */
  { id: "u20", name: "Aissatou Diallo", email: "aissatou.d@edg.gn", role: "chief-service", direction: "reseau" },
  { id: "u30", name: "Saran Bah", email: "saran@edg.gn", role: "chief-service", direction: "reseau", service: "res-ht" },
  /* Communication */
  { id: "u21", name: "Mamadou Diallo", email: "mamadou.d@edg.gn", role: "chief-service", direction: "comm", service: "comm-presse" },
  { id: "u22", name: "Kadiatou Barry", email: "kadi.barry@edg.gn", role: "chief-service", direction: "comm" },
  /* Commerciale */
  { id: "u23", name: "Ousmane Bah", email: "ousmane.bah@edg.gn", role: "chief-service", direction: "dsi", service: "dsi-app" },
  { id: "u24", name: "Sékou Barry", email: "sekou.barry@edg.gn", role: "chief-service", direction: "com" },
  { id: "u28", name: "Lansana Diallo", email: "lansana.d@edg.gn", role: "chief-service", direction: "dsi", service: "dsi-infra" },
  /* Citoyens / agents externes */
  { id: "u25", name: "Mariama Bangoura", email: "mariama.b@gmail.com", role: "user" },
  { id: "u26", name: "Ibrahim Kourouma", email: "ibrahim.k@yahoo.fr", role: "user" },
  { id: "u27", name: "Fatoumata Doumbouya", email: "fatou.doum@gmail.com", role: "user" },
  { id: "u29", name: "Asmaou Diallo", email: "asmaou@edg.gn", role: "user" },
];

export type SmsLogEntry = {
  event: "submitted" | "resolved";
  at: string;
  phone: string;
};

export type TimelineEvent = {
  id: string;
  type: string;
  label: string;
  at: string;
  by?: string;
  actorId?: string;
  actorRole?: string;
  targetUserId?: string;
  targetUserName?: string;
  targetRole?: string;
  oldStatus?: string;
  newStatus?: string;
  comment?: string;
  isPublic?: boolean;
  infos?: Record<string, unknown>;
};

// BR-SLA-REOPEN-001 — un cycle SLA (premier traitement ou après réouverture).
export type SlaCycle = {
  cycleNumber: number;
  startedAt?: string;
  endedAt?: string;
  slaHours?: number;
  elapsedHours?: number;
  responseHours?: number;
  breached?: boolean;
  resolvedBy?: string;
  reopenReason?: string;
  closed: boolean;
};

// BR-TRACE-001 — une intervention (conteneur logique du travail complet d'un
// intervenant, jusqu'à sa transmission ou sa résolution).
export type Intervention = {
  interventionId: string;
  cycleNumber: number;
  interventionOrder?: number;
  actorId?: string;
  actorName?: string;
  actorRole?: string;
  actorMatricule?: string;
  actorDirectionLabel?: string;
  actorDepartmentLabel?: string;
  actorServiceLabel?: string;
  startedAt?: string;
  endedAt?: string;
  durationSeconds?: number;
  workDone?: string;
  instruction?: string;
  transmissionReason?: string;
  decision?: "transmission" | "resolution";
  destinationId?: string;
  destinationName?: string;
  summary?: string;
  solution?: string;
  recommendations?: string;
  slaHours?: number;
  slaBreached?: boolean;
  commentCount: number;
  attachmentCount: number;
  eventIds: string[];
};

export type RequestItem = {
  id: string;
  ref: string;
  title: string;
  description: string;
  status: RequestStatus;
  priority: Priority;
  category: string;
  directionId: string;
  serviceId?: string;
  requesterId: string;
  requesterName: string;
  // Identification du demandeur
  requesterType?: "internal" | "external";
  requesterPhone?: string;
  requesterEmail?: string;
  requesterAddress?: string;
  // Procédure EDG/PS-GSI/Pro-02 tâche 1.3 — descriptif de la solution proposée
  // par le chef de service à l'imputation. Jamais visible du demandeur : servi
  // par la file Distribution (CDS) et par GET /requests/:id/proposed-solution.
  proposedSolution?: string;
  // PV d'intervention (procedure taches 3.3/3.4) — servis par le TSI.
  pvValidatedAt?: string;
  pvSubmittedAt?: string;
  pvArchivedAt?: string;
  intervenantName?: string;
  intervenantBadge?: string;
  // Champs employé EDG (interne)
  employeeMatricule?: string;
  requesterJob?: string;
  requesterDirectionId?: string;
  requesterServiceId?: string;
  // Libellés figés au moment des faits — à préférer aux libellés résolus depuis
  // l'organigramme courant, qui reflètent la situation d'aujourd'hui et non
  // celle du jour de la demande (voir docs/mise-a-jour-backend.md, 2026-09-22).
  requesterDirectionLabel?: string;
  requesterDepartmentLabel?: string;
  requesterServiceLabel?: string;
  handlerDirectionLabel?: string;
  handlerDepartmentLabel?: string;
  handlerServiceLabel?: string;
  // Champs client externe
  meterNumber?: string;
  clientRef?: string;
  siteType?: "domicile" | "commerce" | "administration";
  // Géolocalisation (optionnel — rempli côté client)
  lat?: number;
  lng?: number;
  locationLabel?: string;
  // Triage & SMS
  inTriage?: boolean;
  smsLog?: SmsLogEntry[];
  assigneeId?: string;
  assigneeName?: string;
  isExternal: boolean;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
  isArchived?: boolean;
  resolvedAt?: string;
  closedAt?: string;
  slaHours: number;
  slaElapsed: number;
  // BR-SLA-REOPEN-001 — cycles SLA (détail ticket uniquement, absent des listes).
  slaCycles?: SlaCycle[];
  reopenCount?: number;
  // BR-TRACE-001 — interventions (détail ticket uniquement, absent des listes).
  interventions?: Intervention[];
  // Avatars des intervenants (demandeur, assigné, acteurs/destinataires du journal),
  // cle = account id -> avatar_url (détail ticket uniquement, absent des listes).
  participantAvatars?: Record<string, string>;
  infos?: Record<string, unknown>;
  comments: {
    id: string;
    authorId: string;
    author: string;
    authorRole?: string;
    body: string;
    isPublic: boolean;
    isDirective?: boolean;
    replyToId?: string;
    peerId?: string;
    createdAt: string;
    attachmentId?: string;
    attachmentName?: string;
    attachmentMime?: string;
    attachmentSize?: number;
  }[];
  timeline: TimelineEvent[];
  appreciation?: Appreciation;
};

const now = Date.now();
const h = (n: number) => new Date(now - n * 3600 * 1000).toISOString();

export const requests: RequestItem[] = [
  /* ---- r1-r7 existants ---- */
  {
    id: "r1",
    ref: "EDG-2026-0421",
    title: "Coupure prolongée — quartier Kaloum",
    description:
      "Coupure d'électricité depuis 14h sur l'axe Boulbinet. Plusieurs commerces affectés.",
    status: "in_progress",
    priority: "critical",
    category: "Panne réseau",
    directionId: "reseau",
    serviceId: "res-pannes",
    requesterId: "u9",
    requesterName: "Alpha Diaby",
    requesterType: "external",
    requesterPhone: "+224 622 34 56 78",
    requesterEmail: "alpha.diaby@gmail.com",
    requesterAddress: "Axe Boulbinet, Kaloum — en face de la pharmacie centrale",
    siteType: "commerce",
    smsLog: [{ event: "submitted", at: h(6), phone: "+224 622 34 56 78" }],
    assigneeId: "u7",
    isExternal: true,
    createdAt: h(6),
    updatedAt: h(1),
    slaHours: 4,
    slaElapsed: 6,
    comments: [
      {
        id: "c1",
        authorId: "u7",
        author: "Sékou Condé",
        body: "Équipe technique en intervention sur le transformateur K-12.",
        isPublic: true,
        createdAt: h(2),
      },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(6) },
      { id: "t2", type: "routed", label: "Routée vers Direction Réseau", at: h(6) },
      { id: "t3", type: "assigned", label: "Assignée à Sékou Condé", at: h(5), by: "Fatoumata Bah" },
      { id: "t4", type: "progress", label: "Prise en charge sur site", at: h(2) },
    ],
  },
  {
    id: "r2",
    ref: "EDG-2026-0420",
    title: "Demande d'attestation de consommation",
    description: "Bonjour, j'ai besoin d'une attestation pour mon dossier visa.",
    status: "assigned",
    priority: "medium",
    category: "Document administratif",
    directionId: "com",
    serviceId: "com-clients",
    requesterId: "u10",
    requesterName: "Kadiatou Keita",
    assigneeId: "u8",
    isExternal: true,
    createdAt: h(20),
    updatedAt: h(8),
    slaHours: 48,
    slaElapsed: 20,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(20) },
      { id: "t2", type: "assigned", label: "Assignée à Hadja Sylla", at: h(8) },
    ],
  },
  {
    id: "r3",
    ref: "EDG-2026-0419",
    title: "Réinitialisation accès SAP",
    description: "Mon compte SAP est bloqué après plusieurs tentatives.",
    status: "resolved",
    priority: "high",
    category: "Accès applicatif",
    directionId: "dsi",
    serviceId: "dsi-support",
    requesterId: "u1",
    requesterName: "Mariama Diallo",
    requesterType: "internal",
    requesterEmail: "mariama@edg.gn",
    requesterPhone: "+224 655 12 34 56",
    employeeMatricule: "EDG-2847",
    requesterJob: "Technicienne",
    requesterDirectionId: "dsi",
    requesterServiceId: "dsi-app",
    assigneeId: "u2",
    isExternal: false,
    createdAt: h(72),
    updatedAt: h(48),
    slaHours: 24,
    slaElapsed: 22,
    comments: [
      {
        id: "c1",
        authorId: "u2",
        author: "Ousmane Camara",
        body: "Compte débloqué, nouveau mot de passe temporaire envoyé.",
        isPublic: false,
        createdAt: h(48),
      },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(72) },
      { id: "t2", type: "assigned", label: "Assignée · Chef de service — DSI", at: h(70) },
      { id: "t3", type: "resolved", label: "Résolue", at: h(48), by: "Chef de service — DSI" },
    ],
  },
  {
    id: "r4",
    ref: "EDG-2026-0418",
    title: "Demande de raccordement nouveau site",
    description: "Nous souhaitons raccorder un nouveau site industriel à Coyah.",
    status: "new",
    priority: "high",
    category: "Raccordement",
    directionId: "tech",
    serviceId: "tech-trav",
    requesterId: "u9",
    requesterName: "Alpha Diaby",
    isExternal: true,
    createdAt: h(3),
    updatedAt: h(3),
    slaHours: 72,
    slaElapsed: 3,
    comments: [],
    timeline: [{ id: "t1", type: "created", label: "Ticket créé", at: h(3) }],
  },
  {
    id: "r5",
    ref: "EDG-2026-0417",
    title: "Bulletin de paie introuvable",
    description: "Je n'arrive pas à télécharger mon bulletin de novembre.",
    status: "in_progress",
    priority: "low",
    category: "Paie",
    directionId: "rh",
    serviceId: "rh-paie",
    requesterId: "u1",
    requesterName: "Mariama Diallo",
    assigneeId: "u2",
    isExternal: false,
    createdAt: h(30),
    updatedAt: h(12),
    slaHours: 48,
    slaElapsed: 30,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(30) },
      { id: "t2", type: "pending", label: "En attente du requérant", at: h(12) },
    ],
  },
  {
    id: "r6",
    ref: "EDG-2026-0416",
    title: "Erreur facturation double prélèvement",
    description: "J'ai été prélevé deux fois ce mois-ci.",
    status: "in_progress",
    priority: "high",
    category: "Facturation",
    directionId: "com",
    serviceId: "com-fact",
    requesterId: "u10",
    requesterName: "Kadiatou Keita",
    isExternal: true,
    createdAt: h(50),
    updatedAt: h(4),
    slaHours: 24,
    slaElapsed: 50,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(50) },
      { id: "t2", type: "escalated", label: "Escaladée — SLA dépassé", at: h(4) },
    ],
  },
  {
    id: "r7",
    ref: "EDG-2026-0415",
    title: "Mise à jour antivirus poste direction",
    description: "Antivirus à jour requis avant audit.",
    status: "closed",
    priority: "medium",
    category: "Sécurité",
    directionId: "dsi",
    serviceId: "dsi-infra",
    requesterId: "u5",
    requesterName: "Aïssatou Barry",
    assigneeId: "u2",
    isExternal: false,
    createdAt: h(120),
    updatedAt: h(96),
    slaHours: 24,
    slaElapsed: 18,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(120) },
      { id: "t2", type: "closed", label: "Clôturée", at: h(96) },
    ],
  },
  /* ---- r8-r30 : couverture complète statuts / priorités / directions ---- */
  {
    id: "r8",
    ref: "EDG-2026-0414",
    title: "Panne secteur Dixinn-Centre",
    description: "Coupure signalée depuis ce matin sur Dixinn-Centre.",
    status: "qualifying",
    priority: "medium",
    category: "Panne réseau",
    directionId: "reseau",
    serviceId: "res-pannes",
    requesterId: "u25",
    requesterName: "Mariama Bangoura",
    isExternal: true,
    createdAt: h(2),
    updatedAt: h(1),
    slaHours: 12,
    slaElapsed: 2,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(2) },
      { id: "t2", type: "qualifying", label: "En cours de qualification", at: h(1) },
    ],
  },
  {
    id: "r9",
    ref: "EDG-2026-0413",
    title: "Facture incorrecte — compteur T-0892",
    description: "Montant facturé ne correspond pas à ma consommation réelle.",
    status: "assigned",
    priority: "high",
    category: "Facturation",
    directionId: "com",
    serviceId: "com-fact",
    requesterId: "u26",
    requesterName: "Ibrahim Kourouma",
    isExternal: true,
    createdAt: h(18),
    updatedAt: h(4),
    slaHours: 24,
    slaElapsed: 18,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(18) },
      { id: "t2", type: "qualified", label: "Qualifiée — attente d'affectation", at: h(4) },
    ],
  },
  {
    id: "r10",
    ref: "EDG-2026-0412",
    title: "Demande d'accès applicatif rejetée",
    description: "Accès refusé car hors périmètre de la DSI.",
    status: "rejected",
    priority: "low",
    category: "Accès applicatif",
    directionId: "dsi",
    serviceId: "dsi-support",
    requesterId: "u29",
    requesterName: "Asmaou Diallo",
    isExternal: false,
    createdAt: h(48),
    updatedAt: h(36),
    slaHours: 8,
    slaElapsed: 6,
    comments: [
      { id: "c1", authorId: "u2", author: "Ousmane Camara", body: "Demande hors périmètre — veuillez contacter votre DRH.", isPublic: true, createdAt: h(36) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(48) },
      { id: "t2", type: "rejected", label: "Rejetée — hors périmètre", at: h(36) },
    ],
  },
  {
    id: "r11",
    ref: "EDG-2026-0411",
    title: "Bulletin de paie de mars manquant",
    description: "Mon bulletin de mars n'est pas disponible dans l'espace RH.",
    status: "reopened",
    priority: "medium",
    category: "Paie",
    directionId: "rh",
    serviceId: "rh-paie",
    requesterId: "u1",
    requesterName: "Mariama Diallo",
    assigneeId: "u18",
    isExternal: false,
    createdAt: h(96),
    updatedAt: h(8),
    slaHours: 48,
    slaElapsed: 96,
    comments: [
      { id: "c1", authorId: "u18", author: "Fatoumata Konaté", body: "Bulletin régénéré et disponible.", isPublic: false, createdAt: h(72) },
      { id: "c2", authorId: "u1", author: "Mariama Diallo", body: "Le bulletin est toujours introuvable dans mon espace.", isPublic: true, createdAt: h(8) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(96) },
      { id: "t2", type: "resolved", label: "Marquée résolue", at: h(72) },
      { id: "t3", type: "reopened", label: "Réouvert par le requérant", at: h(8) },
    ],
  },
  {
    id: "r12",
    ref: "EDG-2026-0410",
    title: "Raccordement entrepôt — zone Ratoma",
    description: "Besoin d'un devis pour raccordement haute tension d'un entrepôt frigorifique.",
    status: "qualifying",
    priority: "high",
    category: "Raccordement",
    directionId: "tech",
    serviceId: "tech-trav",
    requesterId: "u26",
    requesterName: "Ibrahim Kourouma",
    isExternal: true,
    createdAt: h(10),
    updatedAt: h(5),
    slaHours: 72,
    slaElapsed: 10,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(10) },
      { id: "t2", type: "qualifying", label: "Qualification en cours", at: h(5) },
    ],
  },
  {
    id: "r13",
    ref: "EDG-2026-0409",
    title: "Mise à jour politique de sécurité réseau",
    description: "Révision des ACL suite à audit interne.",
    status: "in_progress",
    priority: "high",
    category: "Sécurité",
    directionId: "dsi",
    serviceId: "dsi-infra",
    requesterId: "u4",
    requesterName: "Ibrahima Sow",
    assigneeId: "u28",
    isExternal: false,
    createdAt: h(40),
    updatedAt: h(6),
    slaHours: 24,
    slaElapsed: 20,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(40) },
      { id: "t2", type: "assigned", label: "Assignée à Lansana Diallo", at: h(30) },
      { id: "t3", type: "progress", label: "Traitement en cours", at: h(6) },
    ],
  },
  {
    id: "r14",
    ref: "EDG-2026-0408",
    title: "Remboursement frais de mission",
    description: "Notes de frais mission terrain Boké du 2 mai.",
    status: "new",
    priority: "low",
    category: "Remboursement",
    directionId: "fin",
    serviceId: "fin-compta",
    requesterId: "u11",
    requesterName: "Mamadou Barry",
    isExternal: false,
    createdAt: h(1),
    updatedAt: h(1),
    slaHours: 72,
    slaElapsed: 1,
    comments: [],
    timeline: [{ id: "t1", type: "created", label: "Ticket créé", at: h(1) }],
  },
  {
    id: "r15",
    ref: "EDG-2026-0407",
    title: "Publication communiqué panne Conakry",
    description: "Rédaction et diffusion d'un communiqué de presse sur la panne du 4 juin.",
    status: "assigned",
    priority: "medium",
    category: "Communication externe",
    directionId: "comm",
    serviceId: "comm-presse",
    requesterId: "u5",
    requesterName: "Aïssatou Barry",
    assigneeId: "u21",
    isExternal: false,
    createdAt: h(14),
    updatedAt: h(3),
    slaHours: 24,
    slaElapsed: 14,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(14) },
      { id: "t2", type: "assigned", label: "Assignée à Mamadou Diallo", at: h(3) },
    ],
  },
  {
    id: "r16",
    ref: "EDG-2026-0406",
    title: "Demande de congé exceptionnel",
    description: "Congé de 3 jours pour événement familial.",
    status: "in_progress",
    priority: "low",
    category: "Congé",
    directionId: "rh",
    serviceId: "rh-carrieres",
    requesterId: "u11",
    requesterName: "Mamadou Barry",
    assigneeId: "u17",
    isExternal: false,
    createdAt: h(24),
    updatedAt: h(4),
    slaHours: 48,
    slaElapsed: 24,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(24) },
      { id: "t2", type: "assigned", label: "Assignée · Agent — RH", at: h(20) },
      { id: "t3", type: "progress", label: "En cours de validation", at: h(4) },
    ],
  },
  {
    id: "r17",
    ref: "EDG-2026-0405",
    title: "Maintenance préventive transformateur T-22",
    description: "Planification maintenance préventive trimestrielle.",
    status: "in_progress",
    priority: "medium",
    category: "Maintenance",
    directionId: "tech",
    serviceId: "tech-maint",
    requesterId: "u13",
    requesterName: "Boubacar Diallo",
    assigneeId: "u11",
    isExternal: false,
    createdAt: h(60),
    updatedAt: h(20),
    slaHours: 72,
    slaElapsed: 60,
    comments: [
      { id: "c1", authorId: "u11", author: "Mamadou Barry", body: "En attente de la disponibilité de l'équipe externe.", isPublic: false, createdAt: h(20) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(60) },
      { id: "t2", type: "assigned", label: "Assignée à Mamadou Barry", at: h(50) },
      { id: "t3", type: "pending", label: "En attente prestataire", at: h(20) },
    ],
  },
  {
    id: "r18",
    ref: "EDG-2026-0404",
    title: "Accès VPN télétravail",
    description: "Configuration accès VPN pour travail à distance.",
    status: "resolved",
    priority: "medium",
    category: "Accès applicatif",
    directionId: "dsi",
    serviceId: "dsi-app",
    requesterId: "u14",
    requesterName: "Hawa Cissé",
    assigneeId: "u23",
    isExternal: false,
    createdAt: h(56),
    updatedAt: h(40),
    slaHours: 8,
    slaElapsed: 7,
    comments: [
      { id: "c1", authorId: "u23", author: "Ousmane Bah", body: "VPN configuré et testé avec succès.", isPublic: false, createdAt: h(40) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(56) },
      { id: "t2", type: "assigned", label: "Assignée · Chef de service — DSI", at: h(54) },
      { id: "t3", type: "resolved", label: "Résolue", at: h(40), by: "Chef de service — DSI" },
    ],
  },
  {
    id: "r19",
    ref: "EDG-2026-0403",
    title: "Attestation de consommation annuelle",
    description: "Besoin attestation pour dossier bancaire.",
    status: "closed",
    priority: "low",
    category: "Document administratif",
    directionId: "com",
    serviceId: "com-clients",
    requesterId: "u27",
    requesterName: "Fatoumata Doumbouya",
    assigneeId: "u8",
    isExternal: true,
    createdAt: h(200),
    updatedAt: h(160),
    slaHours: 48,
    slaElapsed: 36,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(200) },
      { id: "t2", type: "resolved", label: "Résolue", at: h(170), by: "Hadja Sylla" },
      { id: "t3", type: "closed", label: "Clôturée", at: h(160) },
    ],
  },
  {
    id: "r20",
    ref: "EDG-2026-0402",
    title: "Panne transformateur HT — Matam",
    description: "Transformateur HT en défaut — impact 4 200 abonnés.",
    status: "in_progress",
    priority: "critical",
    category: "Panne réseau",
    directionId: "reseau",
    serviceId: "res-ht",
    requesterId: "u25",
    requesterName: "Mariama Bangoura",
    assigneeId: "u7",
    isExternal: true,
    createdAt: h(18),
    updatedAt: h(2),
    slaHours: 4,
    slaElapsed: 18,
    comments: [
      { id: "c1", authorId: "u7", author: "Sékou Condé", body: "Pièce de remplacement en attente de livraison.", isPublic: true, createdAt: h(10) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(18) },
      { id: "t2", type: "assigned", label: "Assignée à Sékou Condé", at: h(16) },
      { id: "t3", type: "escalated", label: "Escaladée — SLA critique dépassé", at: h(2) },
    ],
  },
  {
    id: "r21",
    ref: "EDG-2026-0401",
    title: "Câblage BT — lotissement Kipé",
    description: "Extension réseau basse tension pour 60 nouveaux abonnés.",
    status: "in_progress",
    priority: "high",
    category: "Travaux réseau",
    directionId: "reseau",
    serviceId: "res-bt",
    requesterId: "u26",
    requesterName: "Ibrahim Kourouma",
    assigneeId: "u7",
    isExternal: true,
    createdAt: h(72),
    updatedAt: h(12),
    slaHours: 120,
    slaElapsed: 72,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(72) },
      { id: "t2", type: "assigned", label: "Assignée à Sékou Condé", at: h(60) },
      { id: "t3", type: "progress", label: "Pose du câblage en cours", at: h(12) },
    ],
  },
  {
    id: "r22",
    ref: "EDG-2026-0400",
    title: "Demande d'avancement de grade",
    description: "Dossier promotion catégorie B → A après 5 ans d'ancienneté.",
    status: "assigned",
    priority: "medium",
    category: "Carrières",
    directionId: "rh",
    serviceId: "rh-carrieres",
    requesterId: "u11",
    requesterName: "Mamadou Barry",
    isExternal: false,
    createdAt: h(80),
    updatedAt: h(24),
    slaHours: 120,
    slaElapsed: 80,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(80) },
      { id: "t2", type: "qualified", label: "Qualifiée — en attente de la commission", at: h(24) },
    ],
  },
  {
    id: "r23",
    ref: "EDG-2026-0399",
    title: "Budget prévisionnel T3 2026",
    description: "Soumission du budget prévisionnel du troisième trimestre.",
    status: "new",
    priority: "medium",
    category: "Budget",
    directionId: "fin",
    serviceId: "fin-budget",
    requesterId: "u15",
    requesterName: "Lansana Traoré",
    isExternal: false,
    createdAt: h(0.5),
    updatedAt: h(0.5),
    slaHours: 96,
    slaElapsed: 1,
    comments: [],
    timeline: [{ id: "t1", type: "created", label: "Ticket créé", at: h(0.5) }],
  },
  {
    id: "r24",
    ref: "EDG-2026-0398",
    title: "Support intégration SAP Finances",
    description: "Erreur de synchronisation module FI lors de la clôture mensuelle.",
    status: "assigned",
    priority: "medium",
    category: "Accès applicatif",
    directionId: "dsi",
    serviceId: "dsi-support",
    requesterId: "u16",
    requesterName: "Ibrahima Bah",
    assigneeId: "u2",
    isExternal: false,
    createdAt: h(22),
    updatedAt: h(6),
    slaHours: 8,
    slaElapsed: 7,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(22) },
      { id: "t2", type: "assigned", label: "Assignée · Chef de service — DSI", at: h(6) },
    ],
  },
  {
    id: "r25",
    ref: "EDG-2026-0397",
    title: "Réclamation facture compteur C-3312",
    description: "Facture reçue pour une adresse qui n'est plus la mienne.",
    status: "qualifying",
    priority: "low",
    category: "Facturation",
    directionId: "com",
    serviceId: "com-clients",
    requesterId: "u27",
    requesterName: "Fatoumata Doumbouya",
    isExternal: true,
    createdAt: h(5),
    updatedAt: h(3),
    slaHours: 48,
    slaElapsed: 5,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(5) },
      { id: "t2", type: "qualifying", label: "Vérification du compteur en cours", at: h(3) },
    ],
  },
  {
    id: "r26",
    ref: "EDG-2026-0396",
    title: "Maintenance préventive groupe électrogène GE-04",
    description: "Vidange et remplacement filtres selon calendrier annuel.",
    status: "resolved",
    priority: "high",
    category: "Maintenance",
    directionId: "tech",
    serviceId: "tech-maint",
    requesterId: "u13",
    requesterName: "Boubacar Diallo",
    assigneeId: "u11",
    isExternal: false,
    createdAt: h(150),
    updatedAt: h(120),
    slaHours: 48,
    slaElapsed: 30,
    comments: [
      { id: "c1", authorId: "u11", author: "Mamadou Barry", body: "Maintenance effectuée, rapport joint.", isPublic: false, createdAt: h(120) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(150) },
      { id: "t2", type: "assigned", label: "Assignée à Mamadou Barry", at: h(145) },
      { id: "t3", type: "resolved", label: "Résolue", at: h(120), by: "Mamadou Barry" },
    ],
  },
  {
    id: "r27",
    ref: "EDG-2026-0395",
    title: "Interruption réseau critique — Almamya",
    description: "Coupure totale secteur Almamya, deuxième incident ce mois.",
    status: "reopened",
    priority: "critical",
    category: "Panne réseau",
    directionId: "reseau",
    serviceId: "res-pannes",
    requesterId: "u9",
    requesterName: "Alpha Diaby",
    assigneeId: "u7",
    isExternal: true,
    createdAt: h(36),
    updatedAt: h(4),
    slaHours: 4,
    slaElapsed: 36,
    comments: [
      { id: "c1", authorId: "u7", author: "Sékou Condé", body: "Première intervention terminée — alimentation rétablie à 80%.", isPublic: true, createdAt: h(24) },
      { id: "c2", authorId: "u9", author: "Alpha Diaby", body: "Nouvelle coupure ce matin, problème non résolu.", isPublic: true, createdAt: h(4) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(36) },
      { id: "t2", type: "resolved", label: "Marquée résolue", at: h(24) },
      { id: "t3", type: "reopened", label: "Réouvert par le requérant", at: h(4) },
    ],
  },
  {
    id: "r28",
    ref: "EDG-2026-0394",
    title: "Bulletin de salaire avril manquant",
    description: "Le bulletin d'avril n'apparaît pas dans le portail paie.",
    status: "in_progress",
    priority: "medium",
    category: "Paie",
    directionId: "rh",
    serviceId: "rh-paie",
    requesterId: "u14",
    requesterName: "Hawa Cissé",
    assigneeId: "u18",
    isExternal: false,
    createdAt: h(42),
    updatedAt: h(18),
    slaHours: 48,
    slaElapsed: 42,
    comments: [
      { id: "c1", authorId: "u18", author: "Fatoumata Konaté", body: "En attente de la validation du fichier de paie par le directeur.", isPublic: false, createdAt: h(18) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(42) },
      { id: "t2", type: "assigned", label: "Assignée à Fatoumata Konaté", at: h(38) },
      { id: "t3", type: "pending", label: "En attente validation direction", at: h(18) },
    ],
  },
  {
    id: "r29",
    ref: "EDG-2026-0393",
    title: "Demande d'accès audit interne",
    description: "Accès aux journaux système pour audit externe rejeté.",
    status: "rejected",
    priority: "low",
    category: "Sécurité",
    directionId: "dsi",
    serviceId: "dsi-infra",
    requesterId: "u6",
    requesterName: "Mohamed Touré",
    isExternal: false,
    createdAt: h(168),
    updatedAt: h(144),
    slaHours: 6,
    slaElapsed: 4,
    comments: [
      { id: "c1", authorId: "u28", author: "Lansana Diallo", body: "Accès refusé — habilitation auditeur externe non signée.", isPublic: false, createdAt: h(144) },
    ],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(168) },
      { id: "t2", type: "rejected", label: "Rejetée — habilitation manquante", at: h(144) },
    ],
  },
  /* ---- Demandes en attente de tri (inTriage: true) ---- */
  {
    id: "rtriage1",
    ref: "EDG-2026-0391",
    title: "Coupure totale — quartier Hamdallaye",
    description: "Pas d'électricité depuis hier soir 22h dans tout le quartier Hamdallaye. Les voisins sont aussi affectés. Repère : en face du marché.",
    status: "new",
    priority: "high",
    category: "Panne réseau",
    directionId: "",
    requesterId: "ext-1",
    requesterName: "Boubacar Camara",
    requesterType: "external",
    requesterPhone: "+224 628 45 67 89",
    requesterEmail: "b.camara@gmail.com",
    requesterAddress: "Hamdallaye ACI, en face du marché central — Conakry",
    siteType: "domicile",
    meterNumber: "MT-08823",
    inTriage: true,
    smsLog: [{ event: "submitted", at: h(0.3), phone: "+224 628 45 67 89" }],
    isExternal: true,
    createdAt: h(0.3),
    updatedAt: h(0.3),
    slaHours: 4,
    slaElapsed: 0,
    comments: [],
    timeline: [{ id: "t1", type: "created", label: "Ticket déposé sans compte (citoyen)", at: h(0.3) }],
  },
  {
    id: "rtriage2",
    ref: "EDG-2026-0390",
    title: "Réclamation sur facture — montant anormal",
    description: "Ma facture de mai est 3 fois plus élevée que d'habitude. Je n'ai pas changé mes habitudes de consommation. Mon compteur est C-4471.",
    status: "new",
    priority: "medium",
    category: "Facturation",
    directionId: "",
    requesterId: "ext-2",
    requesterName: "Aminata Kourouma",
    requesterType: "external",
    requesterPhone: "+224 664 98 76 54",
    requesterEmail: "aminata.k@yahoo.fr",
    requesterAddress: "Coleah, rue des Flamboyants — Conakry",
    siteType: "domicile",
    meterNumber: "C-4471",
    clientRef: "CL-20293",
    inTriage: true,
    smsLog: [{ event: "submitted", at: h(1.5), phone: "+224 664 98 76 54" }],
    isExternal: true,
    createdAt: h(1.5),
    updatedAt: h(1.5),
    slaHours: 48,
    slaElapsed: 2,
    comments: [],
    timeline: [{ id: "t1", type: "created", label: "Ticket déposé sans compte (citoyen)", at: h(1.5) }],
  },
  {
    id: "rtriage3",
    ref: "EDG-2026-0389",
    title: "Demande de raccordement — nouvel entrepôt",
    description: "Je souhaite raccorder mon entrepôt frigorifique en construction à Matoto. Surface : 800m². Besoin d'un devis et d'une estimation des délais.",
    status: "new",
    priority: "low",
    category: "Raccordement",
    directionId: "",
    requesterId: "ext-3",
    requesterName: "Ibrahima Sylla",
    requesterType: "external",
    requesterPhone: "+224 620 11 22 33",
    requesterEmail: "ibrahima.sylla@commerce.gn",
    requesterAddress: "Zone industrielle Matoto, lot 14B — Conakry",
    siteType: "commerce",
    inTriage: true,
    smsLog: [{ event: "submitted", at: h(3), phone: "+224 620 11 22 33" }],
    isExternal: true,
    createdAt: h(3),
    updatedAt: h(3),
    slaHours: 72,
    slaElapsed: 3,
    comments: [],
    timeline: [{ id: "t1", type: "created", label: "Ticket déposé sans compte (citoyen)", at: h(3) }],
  },
  {
    id: "r30",
    ref: "EDG-2026-0392",
    title: "Erreur de facturation réglée — dossier clos",
    description: "Erreur de double facturation corrigée après vérification.",
    status: "closed",
    priority: "medium",
    category: "Facturation",
    directionId: "com",
    serviceId: "com-fact",
    requesterId: "u10",
    requesterName: "Kadiatou Keita",
    assigneeId: "u8",
    isExternal: true,
    createdAt: h(240),
    updatedAt: h(200),
    slaHours: 24,
    slaElapsed: 20,
    comments: [],
    timeline: [
      { id: "t1", type: "created", label: "Ticket créé", at: h(240) },
      { id: "t2", type: "resolved", label: "Résolue — remboursement émis", at: h(210) },
      { id: "t3", type: "closed", label: "Clôturée", at: h(200) },
    ],
  },
];

export const statusLabels: Record<RequestStatus, string> = {
  new: "Nouvelle",
  qualifying: "En qualification",
  assigned: "Assignée",
  in_progress: "En cours",
  resolved: "Résolue",
  closed: "Clôturée",
  reopened: "Réouverte",
  rejected: "Rejetée",
  cancelled: "Annulée",
};

export const priorityLabels: Record<Priority, string> = {
  low: "Basse",
  medium: "Moyenne",
  high: "Haute",
  critical: "Critique",
};

// ── Gestion dynamique des niveaux de priorité (admin CRUD) ────────────────
export type PriorityColor =
  | "slate"
  | "blue"
  | "teal"
  | "amber"
  | "orange"
  | "red"
  | "purple";

export const priorityColorMap: Record<
  PriorityColor,
  { badge: string; dot: string; label: string }
> = {
  slate:  { badge: "bg-muted text-muted-foreground",                                        dot: "bg-slate-400",  label: "Gris" },
  blue:   { badge: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",     dot: "bg-blue-500",   label: "Bleu" },
  teal:   { badge: "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",     dot: "bg-teal-500",   label: "Sarcelle" },
  amber:  { badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400", dot: "bg-amber-500",  label: "Ambre" },
  orange: { badge: "bg-warning/20 text-warning-foreground dark:text-warning",               dot: "bg-orange-500", label: "Orange" },
  red:    { badge: "bg-destructive/15 text-destructive",                                    dot: "bg-red-500",    label: "Rouge" },
  purple: { badge: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400", dot: "bg-purple-500", label: "Violet" },
};

export interface PriorityDefinition {
  id: string;
  slug: string;        // identifiant technique (ex. "low", "urgent")
  label: string;       // libellé affiché dans les formulaires et badges
  description: string; // explication métier
  color: PriorityColor;
  order: number;       // rang de gravité croissant (1 = le moins urgent)
  active: boolean;
  isBuiltin: boolean;  // les 4 priorités de base ne peuvent pas être supprimées
}

export const priorityDefinitions: PriorityDefinition[] = [
  {
    id: "pd1",
    slug: "low",
    label: "Basse",
    description: "Tickets non urgents, traitement dans les délais standards.",
    color: "slate",
    order: 1,
    active: true,
    isBuiltin: true,
  },
  {
    id: "pd2",
    slug: "medium",
    label: "Moyenne",
    description: "Tickets courants nécessitant un suivi normal.",
    color: "blue",
    order: 2,
    active: true,
    isBuiltin: true,
  },
  {
    id: "pd3",
    slug: "high",
    label: "Haute",
    description: "Tickets urgents impactant plusieurs utilisateurs ou services.",
    color: "orange",
    order: 3,
    active: true,
    isBuiltin: true,
  },
  {
    id: "pd4",
    slug: "critical",
    label: "Critique",
    description: "Incidents majeurs à traiter immédiatement — impact fort ou sécurité.",
    color: "red",
    order: 4,
    active: true,
    isBuiltin: true,
  },
];

export const roleLabels: Record<Role, string> = {
  public: "Public",
  user: "Utilisateur",
  "chief-service": "Chef de Service",
  technicien: "Technicien",
  "chef-division-support": "Chef de Division Support",
  admin: "Administrateur",
};

export function getDirection(id?: string) {
  return directions.find((d) => d.id === id);
}

export function getUserByMatricule(matricule: string): AppUser | undefined {
  return users.find((u) => u.matricule === matricule.trim().toUpperCase());
}

/* ------------------------------------------------------------------ */
/* Supervision — SLA par agent                                         */
/* ------------------------------------------------------------------ */

export type AgentSLA = {
  id: string;
  name: string;
  avatar?: string;
  direction: string;
  service: string;
  open: number;
  handled: number;
  avgResolutionH: number;
  slaRespect: number; // 0-100
  satisfaction: number; // 0-5
  status: "available" | "busy" | "overload" | "off";
};

export const agentSLAs: AgentSLA[] = [
  { id: "u2", name: "Ousmane Camara", direction: "DSI", service: "Support utilisateurs", open: 6, handled: 124, avgResolutionH: 3.2, slaRespect: 94, satisfaction: 4.7, status: "available" },
  { id: "u7", name: "Sékou Condé", direction: "Réseau", service: "Cellule pannes", open: 11, handled: 218, avgResolutionH: 5.8, slaRespect: 78, satisfaction: 4.3, status: "overload" },
  { id: "u8", name: "Hadja Sylla", direction: "Commerciale", service: "Service Clients", open: 4, handled: 96, avgResolutionH: 12.4, slaRespect: 88, satisfaction: 4.5, status: "busy" },
  { id: "a4", name: "Aïcha Bangoura", direction: "DSI", service: "Applications métier", open: 7, handled: 154, avgResolutionH: 4.1, slaRespect: 91, satisfaction: 4.6, status: "available" },
  { id: "a5", name: "Mamadou Sylla", direction: "Technique", service: "Maintenance", open: 9, handled: 187, avgResolutionH: 6.7, slaRespect: 72, satisfaction: 3.9, status: "overload" },
  { id: "a6", name: "Fanta Diallo", direction: "Commerciale", service: "Facturation", open: 3, handled: 142, avgResolutionH: 8.2, slaRespect: 96, satisfaction: 4.8, status: "available" },
  { id: "a7", name: "Lansana Camara", direction: "Réseau", service: "Basse tension", open: 5, handled: 110, avgResolutionH: 7.5, slaRespect: 83, satisfaction: 4.2, status: "busy" },
  { id: "a8", name: "Aminata Touré", direction: "RH", service: "Paie", open: 2, handled: 78, avgResolutionH: 14.0, slaRespect: 89, satisfaction: 4.4, status: "off" },
];

/* ------------------------------------------------------------------ */
/* SLA & priorités configurables                                       */
/* ------------------------------------------------------------------ */

export type SLAPolicy = {
  id: string;
  category: string;
  priority: Priority;
  responseH: number;
  resolutionH: number;
  escalateAfterH: number;
  active: boolean;
};

export const slaPolicies: SLAPolicy[] = [
  { id: "sla1", category: "Panne réseau", priority: "critical", responseH: 1, resolutionH: 4, escalateAfterH: 2, active: true },
  { id: "sla2", category: "Panne réseau", priority: "high", responseH: 2, resolutionH: 12, escalateAfterH: 8, active: true },
  { id: "sla3", category: "Facturation", priority: "high", responseH: 4, resolutionH: 24, escalateAfterH: 16, active: true },
  { id: "sla4", category: "Facturation", priority: "medium", responseH: 8, resolutionH: 48, escalateAfterH: 36, active: true },
  { id: "sla5", category: "Document administratif", priority: "medium", responseH: 12, resolutionH: 48, escalateAfterH: 40, active: true },
  { id: "sla6", category: "Raccordement", priority: "high", responseH: 8, resolutionH: 72, escalateAfterH: 60, active: true },
  { id: "sla7", category: "Accès applicatif", priority: "high", responseH: 2, resolutionH: 8, escalateAfterH: 6, active: true },
  { id: "sla8", category: "Sécurité", priority: "critical", responseH: 1, resolutionH: 6, escalateAfterH: 3, active: false },
];

/* ------------------------------------------------------------------ */
/* Règles de routage                                                   */
/* ------------------------------------------------------------------ */

export type RoutingRule = {
  id: string;
  name: string;
  conditionField: "category" | "priority" | "source" | "keyword";
  conditionValue: string;
  targetDirection: string;
  targetService: string;
  targetServiceLabel?: string;
  autoAssign: boolean;
  active: boolean;
  order: number;
};

export const routingRules: RoutingRule[] = [
  { id: "r1", name: "Pannes critiques → Cellule pannes", conditionField: "category", conditionValue: "Panne réseau", targetDirection: "Réseau", targetService: "Cellule pannes", autoAssign: true, active: true, order: 1 },
  { id: "r2", name: "Facturation → Service Clients", conditionField: "category", conditionValue: "Facturation", targetDirection: "Commerciale", targetService: "Facturation", autoAssign: true, active: true, order: 2 },
  { id: "r3", name: "Documents administratifs", conditionField: "category", conditionValue: "Document administratif", targetDirection: "Commerciale", targetService: "Service Clients", autoAssign: false, active: true, order: 3 },
  { id: "r4", name: "Raccordement → Travaux", conditionField: "category", conditionValue: "Raccordement", targetDirection: "Technique", targetService: "Travaux", autoAssign: true, active: true, order: 4 },
  { id: "r5", name: "Mots-clés « SAP » ou « ERP »", conditionField: "keyword", conditionValue: "SAP,ERP,applicatif", targetDirection: "DSI", targetService: "Applications métier", autoAssign: true, active: true, order: 5 },
  { id: "r6", name: "Priorité critique → Chef de service", conditionField: "priority", conditionValue: "critical", targetDirection: "—", targetService: "Escalade L2", autoAssign: false, active: true, order: 6 },
  { id: "r7", name: "Source agence physique", conditionField: "source", conditionValue: "Agence", targetDirection: "Commerciale", targetService: "Service Clients", autoAssign: false, active: false, order: 7 },
];

/* ------------------------------------------------------------------ */
/* Journaux d'activité                                                 */
/* ------------------------------------------------------------------ */

export type ActivityLog = {
  id: string;
  at: string;
  actor: string;
  actorRole: Role;
  action: string;
  category: "auth" | "request" | "admin" | "system" | "security";
  target: string;
  ip: string;
  userAgent: string;
  status: "success" | "warning" | "error";
  metadata: Record<string, unknown>;
};

const ua = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36";
export const activityLogs: ActivityLog[] = [
  { id: "l1", at: h(0.2), actor: "Mohamed Touré", actorRole: "admin", action: "Modification du rôle utilisateur", category: "admin", target: "u3 → chief-service", ip: "196.207.84.12", userAgent: ua, status: "success", metadata: { from: "user", to: "chief-service", user_id: "u3", reason: "Promotion service" } },
  { id: "l2", at: h(0.5), actor: "Sékou Condé", actorRole: "chief-service", action: "Mise à jour du statut ticket", category: "request", target: "EDG-2026-0421", ip: "10.12.3.44", userAgent: ua, status: "success", metadata: { ref: "EDG-2026-0421", previous_status: "qualifying", new_status: "in_progress", sla_ok: true } },
  { id: "l3", at: h(0.7), actor: "system", actorRole: "admin", action: "Escalade automatique", category: "system", target: "EDG-2026-0416", ip: "—", userAgent: "edg-engine/1.4", status: "warning", metadata: { rule: "SLA dépassé > 24h", level: "L3", sla_breach_h: 31.5, escalated_to: "Fatoumata Bah" } },
  { id: "l4", at: h(1.1), actor: "Aïssatou Barry", actorRole: "chief-service", action: "Connexion réussie", category: "auth", target: "—", ip: "41.83.12.7", userAgent: ua, status: "success", metadata: { mfa: true, session_id: "sess_8f2a3c" } },
  { id: "l5", at: h(1.4), actor: "anon", actorRole: "public", action: "Échec d'authentification", category: "security", target: "admin@edg.gn", ip: "185.34.220.18", userAgent: "curl/8.4", status: "error", metadata: { attempts: 5, blocked: true, ip_country: "RU", lockout_min: 30 } },
  { id: "l6", at: h(2.2), actor: "Fatoumata Bah", actorRole: "chief-service", action: "Assignation de ticket", category: "request", target: "EDG-2026-0420 → Hadja Sylla", ip: "10.12.7.89", userAgent: ua, status: "success", metadata: { ref: "EDG-2026-0420", assigned_to: "u7", agent_name: "Hadja Sylla", team: "Service client" } },
  { id: "l7", at: h(3.0), actor: "Mohamed Touré", actorRole: "admin", action: "Modification SLA", category: "admin", target: "Panne réseau · critical", ip: "196.207.84.12", userAgent: ua, status: "success", metadata: { responseH: 1, resolutionH: 4, previous_responseH: 2, previous_resolutionH: 8 } },
  { id: "l8", at: h(4.5), actor: "Alpha Diaby", actorRole: "user", action: "Création de ticket", category: "request", target: "EDG-2026-0418", ip: "102.130.45.7", userAgent: "EDG-Mobile/2.1", status: "success", metadata: { ref: "EDG-2026-0418", channel: "mobile", attachments: 2 } },
  { id: "l9", at: h(6.8), actor: "system", actorRole: "admin", action: "Sauvegarde quotidienne", category: "system", target: "PostgreSQL", ip: "—", userAgent: "edg-backup/2.0", status: "success", metadata: { size_mb: 412, tables: 18, success: true, compressed: true, duration_min: 4 } },
  { id: "l10", at: h(8.2), actor: "Ousmane Camara", actorRole: "chief-service", action: "Clôture de ticket", category: "request", target: "EDG-2026-0419", ip: "10.12.3.55", userAgent: ua, status: "success", metadata: { ref: "EDG-2026-0419", resolution_h: 22, csat_rating: 4, sla_ok: true } },
  { id: "l11", at: h(9.3), actor: "Mohamed Touré", actorRole: "admin", action: "Création règle de routage", category: "admin", target: "Mots-clés SAP/ERP", ip: "196.207.84.12", userAgent: ua, status: "success", metadata: { rule_id: "r5", keywords: ["SAP", "ERP", "SIRH"], target_service: "DSI" } },
  { id: "l12", at: h(14.0), actor: "system", actorRole: "admin", action: "Indisponibilité partielle", category: "system", target: "module notifications", ip: "—", userAgent: "edg-monitor/1.0", status: "warning", metadata: { duration_min: 7, affected_users: 43, auto_recovered: true } },
  { id: "l13", at: h(22.5), actor: "Mariama Diallo", actorRole: "user", action: "Connexion réussie", category: "auth", target: "—", ip: "102.130.55.2", userAgent: ua, status: "success", metadata: { mfa: false, device: "web" } },
  { id: "l14", at: h(26.0), actor: "anon", actorRole: "public", action: "Tentative SQL injection détectée", category: "security", target: "/api/requests", ip: "45.142.122.9", userAgent: "sqlmap/1.7", status: "error", metadata: { blocked: true, fingerprint: "WAF-018", payload: "' OR 1=1--", waf_rule: "SQL001", ip_country: "CN" } },
  { id: "l15", at: h(36.0), actor: "Mohamed Touré", actorRole: "admin", action: "Publication article KB", category: "admin", target: "k1 — Comment signaler une coupure", ip: "196.207.84.12", userAgent: ua, status: "success", metadata: { article_id: "k1", visible_to: ["user", "public"], tags: ["coupure", "signalement"] } },
];

export const logCategoryLabels: Record<ActivityLog["category"], string> = {
  auth: "Authentification",
  request: "Tickets",
  admin: "Administration",
  system: "Système",
  security: "Sécurité",
};

/* ------------------------------------------------------------------ */
/* Helpers analytics pour les dashboards Directeur                    */
/* ------------------------------------------------------------------ */

const CLOSED_STATUSES: RequestStatus[] = ["resolved", "closed", "rejected"];

export type DirectionStat = {
  id: string;
  name: string;
  total: number;
  open: number;
  resolved: number;
  overdue: number;
  slaRespect: number;
};

export function directionStats(): DirectionStat[] {
  return directions.map((d) => {
    const reqs = requests.filter((r) => r.directionId === d.id);
    const open = reqs.filter((r) => !CLOSED_STATUSES.includes(r.status)).length;
    const resolved = reqs.filter((r) => r.status === "resolved" || r.status === "closed").length;
    const overdue = reqs.filter((r) => r.slaElapsed > r.slaHours).length;
    const slaRespect =
      reqs.length > 0
        ? Math.round((reqs.filter((r) => r.slaElapsed <= r.slaHours).length / reqs.length) * 100)
        : 100;
    return { id: d.id, name: d.name, total: reqs.length, open, resolved, overdue, slaRespect };
  });
}

export type ServiceStat = {
  id: string;
  name: string;
  total: number;
  open: number;
  resolved: number;
  overdue: number;
  slaRespect: number;
};

export function serviceStats(directionId: string): ServiceStat[] {
  const dir = directions.find((d) => d.id === directionId);
  if (!dir) return [];
  return dir.services.map((s) => {
    const reqs = requests.filter((r) => r.serviceId === s.id);
    const open = reqs.filter((r) => !CLOSED_STATUSES.includes(r.status)).length;
    const resolved = reqs.filter((r) => r.status === "resolved" || r.status === "closed").length;
    const overdue = reqs.filter((r) => r.slaElapsed > r.slaHours).length;
    const slaRespect =
      reqs.length > 0
        ? Math.round((reqs.filter((r) => r.slaElapsed <= r.slaHours).length / reqs.length) * 100)
        : 100;
    return { id: s.id, name: s.name, total: reqs.length, open, resolved, overdue, slaRespect };
  });
}

export type StatusBreakdownItem = { status: RequestStatus; label: string; value: number };

export function statusBreakdown(reqs: RequestItem[]): StatusBreakdownItem[] {
  const counts: Partial<Record<RequestStatus, number>> = {};
  for (const r of reqs) {
    counts[r.status] = (counts[r.status] ?? 0) + 1;
  }
  return (Object.keys(counts) as RequestStatus[])
    .filter((s) => (counts[s] ?? 0) > 0)
    .map((s) => ({ status: s, label: statusLabels[s], value: counts[s]! }));
}

/* ================================================================== */
/* CSAT — Note d'appréciation par le demandeur                        */
/* ================================================================== */

export type Appreciation = {
  rating: 1 | 2 | 3 | 4 | 5;
  comment?: string;
  resolvedConfirmed: boolean;
  authorType: "internal" | "external";
  at: string;
};

/* Ajoute des appréciations à quelques demandes résolues/clôturées */
const _applyAppreciations = () => {
  const map: Record<string, Appreciation> = {
    r3:  { rating: 5, comment: "Très rapide et efficace, compte débloqué en moins d'une journée.", resolvedConfirmed: true, authorType: "internal",  at: h(46) },
    r7:  { rating: 4, resolvedConfirmed: true, authorType: "internal",  at: h(94) },
    r18: { rating: 4, comment: "Merci, VPN configuré rapidement.", resolvedConfirmed: true, authorType: "internal",  at: h(38) },
    r19: { rating: 3, comment: "Délai assez long mais le document est bien arrivé.", resolvedConfirmed: true, authorType: "external", at: h(165) },
    r26: { rating: 5, comment: "Excellent travail, maintenance effectuée dans les temps.", resolvedConfirmed: true, authorType: "internal",  at: h(118) },
    r30: { rating: 2, comment: "Remboursement trop lent, j'ai dû rappeler plusieurs fois.", resolvedConfirmed: false, authorType: "external", at: h(198) },
  };
  for (const req of requests) {
    if (map[req.id]) req.appreciation = map[req.id];
  }
};
_applyAppreciations();

export type CsatStat = {
  key: string;
  label: string;
  avg: number;
  count: number;
  external: number;
  internal: number;
};

export function csatStats(): {
  global: number;
  byDirection: CsatStat[];
  byCategory: CsatStat[];
  byAgent: CsatStat[];
} {
  const rated = requests.filter((r) => r.appreciation);

  const avg = (reqs: typeof requests) => {
    const r2 = reqs.filter((r) => r.appreciation);
    if (!r2.length) return 0;
    return Math.round((r2.reduce((s, r) => s + (r.appreciation!.rating), 0) / r2.length) * 10) / 10;
  };

  const global = avg(rated);

  const byDirection: CsatStat[] = directions.map((d) => {
    const reqs = rated.filter((r) => r.directionId === d.id && r.appreciation);
    const ext = reqs.filter((r) => r.appreciation!.authorType === "external").length;
    const int = reqs.filter((r) => r.appreciation!.authorType === "internal").length;
    return { key: d.id, label: d.name, avg: avg(reqs), count: reqs.length, external: ext, internal: int };
  }).filter((s) => s.count > 0);

  const categories = [...new Set(rated.filter(r => r.appreciation).map((r) => r.category))];
  const byCategory: CsatStat[] = categories.map((cat) => {
    const reqs = rated.filter((r) => r.category === cat && r.appreciation);
    const ext = reqs.filter((r) => r.appreciation!.authorType === "external").length;
    const int = reqs.filter((r) => r.appreciation!.authorType === "internal").length;
    return { key: cat, label: cat, avg: avg(reqs), count: reqs.length, external: ext, internal: int };
  });

  const agentIds = [...new Set(rated.filter(r => r.assigneeId && r.appreciation).map((r) => r.assigneeId!))];
  const byAgent: CsatStat[] = agentIds.map((aid) => {
    const agent = users.find((u) => u.id === aid);
    const reqs = rated.filter((r) => r.assigneeId === aid && r.appreciation);
    const ext = reqs.filter((r) => r.appreciation!.authorType === "external").length;
    const int = reqs.filter((r) => r.appreciation!.authorType === "internal").length;
    return {
      key: aid,
      label: agent?.name ?? aid,
      avg: avg(reqs),
      count: reqs.length,
      external: ext,
      internal: int,
    };
  });

  return { global, byDirection, byCategory, byAgent };
}

/* ================================================================== */
/* COMMUNICATION INSTITUTIONNELLE                                      */
/* ================================================================== */



