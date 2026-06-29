import { createFileRoute, Link } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { WorkflowTimeline } from "@/components/workflow-timeline";
import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import type { RequestItem, Appreciation } from "@/lib/mock-data";
import { AppreciationForm } from "@/components/appreciation-form";
import {
  EscalationProgressBar,
  buildStepsFromStatus,
  buildRequesterStepsFromStatus,
  DEFAULT_LEVELS,
} from "@/components/escalation-progress-bar";
import { useRole, useUser } from "@/lib/session";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  fetchRequest,
  resolveRequest,
  assignRequest,
  createComment,
  requestReopen,
  reopenRequest,
  closeRequest,
  updateRequest,
  cancelRequest,
  escalateRequest,
  uploadAttachment,
  mergeRequest,
  duplicateRequest,
  rejectTicket,
  requesterEditRequest,
} from "@/lib/api/requests";
import { fetchRefTable, fetchRequestCategories } from "@/lib/api/admin-config";
import { fetchUser, fetchUsers } from "@/lib/api/accounts";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Direction, Unit } from "@/lib/api/directions-units";
import { submitAppreciation, updateRequestAppreciation } from "@/lib/api/csat";
import {
  fetchRequestWorkflows,
  fetchWorkflowDetails,
  fetchRequestTasks,
  createTask,
  approveTask,
  rejectTask,
  cancelTask,
  acceptWorkflowDetailById,
  createAutoCircuit,
  type WorkflowItem,
  type WorkflowDetailItem,
  type TaskItem,
} from "@/lib/api/workflow";

import {
  ArrowLeft,
  Clock,
  Paperclip,
  User,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  Building2,
  Mail,
  MapPin,
  Phone,
  BadgeCheck,
  Users,
  UserCheck,
  ChevronDown,
  Lock,
  Loader2,
  GitBranch,
  ListTodo,
  Plus,
  X,
  XCircle,
  RotateCcw,
  Pencil,
  Ban,
  MessageSquareWarning,
  GitMerge,
  Copy,
} from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { isRequester } from "@/lib/capabilities";

export const Route = createFileRoute("/app/requests/$id")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Détail demande — EDG Support" }] }),
  component: RequestDetail,
  notFoundComponent: () => (
    <div className="mx-auto max-w-md p-10 text-center">
      <h2 className="text-lg font-semibold">Demande introuvable</h2>
      <Button asChild variant="outline" className="mt-4 rounded-full">
        <Link to="/app/requests">Retour aux demandes</Link>
      </Button>
    </div>
  ),
});

function RequestDetail() {
  const { id } = Route.useParams();
  const qc = useQueryClient();
  const sessionUser = useUser();
  const authorId = Number(sessionUser?.id ?? 0);
  const authorName = [sessionUser?.firstname, sessionUser?.name].filter(Boolean).join(" ") || "Agent";

  const { data: r, isLoading, isError } = useQuery({
    queryKey: ["request", id],
    queryFn: () => fetchRequest(id),
    staleTime: 15_000,
  });

  const [comment, setComment] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [role] = useRole();
  // Algo 1 — ownership-based perspective: le rôle détermine ce qu'on peut FAIRE,
  // mais si l'utilisateur est le demandeur du ticket (quel que soit son rôle),
  // il voit la vue requester (suivi de sa demande, pas les outils de traitement).
  const iAmRequester = isRequester(r?.requesterId, sessionUser?.id);
  const isRequesterView = role === "user" || iAmRequester;
  const isChief = role === "chief";
  const isDirector = role === "director";
  const isAgentOnly = role === "agent" && !iAmRequester;
  const canManageStatus = !iAmRequester && (role === "agent" || role === "chief" || role === "director" || role === "admin");
  const canAssign = !iAmRequester && (role === "agent" || role === "chief" || role === "admin");
  const [localAppreciation, setLocalAppreciation] = useState<Appreciation | undefined>(undefined);
  const [showReassign, setShowReassign] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskType, setTaskType] = useState<"reassignment" | "reopening">("reassignment");
  const [taskReason, setTaskReason] = useState("");
  const [reopenReason, setReopenReason] = useState("");
  const [showReopenForm, setShowReopenForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editPriority, setEditPriority] = useState("");
  const [editDirectionId, setEditDirectionId] = useState("");
  const [editServiceId, setEditServiceId] = useState("");
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [showRequestInfoForm, setShowRequestInfoForm] = useState(false);
  const [infoQuestion, setInfoQuestion] = useState("");
  const [showResolveForm, setShowResolveForm] = useState(false);
  const [resolutionNote, setResolutionNote] = useState("");
  const [showEscalateForm, setShowEscalateForm] = useState(false);
  const [escalateLevel, setEscalateLevel] = useState<string>(DEFAULT_LEVELS[3] ?? "Chef de service");
  const [escalateReason, setEscalateReason] = useState("");
  const attachRef = useRef<HTMLInputElement>(null);
  const commentRef = useRef<HTMLTextAreaElement>(null);
  const [showPriorityPicker, setShowPriorityPicker] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [showServicePicker, setShowServicePicker] = useState(false);
  const [showMergeDialog, setShowMergeDialog] = useState(false);
  const [mergeTargetId, setMergeTargetId] = useState("");
  const [acceptingStepId, setAcceptingStepId] = useState<string | null>(null);
  const [acceptDialogMode, setAcceptDialogMode] = useState<"accept" | "refuse">("accept");
  const [acceptComment, setAcceptComment] = useState("");
  const [showCircuitDialog, setShowCircuitDialog] = useState(false);
  const [circuitDirectionId, setCircuitDirectionId] = useState("");
  const [circuitUnitId, setCircuitUnitId] = useState("");

  const invalidate = () => {
    // Détail du ticket (et sous-queries via préfixe)
    qc.invalidateQueries({ queryKey: ["request", id] });
    // Toutes les listes/vues qui peuvent contenir ce ticket
    qc.invalidateQueries({ queryKey: ["requests"] });
    qc.invalidateQueries({ queryKey: ["queue"] });
    qc.invalidateQueries({ queryKey: ["my-tickets"] });
    qc.invalidateQueries({ queryKey: ["my-tickets-stats"] });
    qc.invalidateQueries({ queryKey: ["my-stats", sessionUser?.id] });
    // Stats et tableaux de bord
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
    qc.invalidateQueries({ queryKey: ["sla-center"] });
  };
  const invalidateTasks = () => qc.invalidateQueries({ queryKey: ["request", id, "tasks"] });
  const invalidateWorkflows = () => {
    qc.invalidateQueries({ queryKey: ["request", id, "workflows"] });
    qc.invalidateQueries({ queryKey: ["workflow"] });
  };

  const resolveMut = useMutation({
    mutationFn: async () => {
      if (resolutionNote.trim()) {
        await createComment(id, {
          author_id: authorId,
          author_name: authorName,
          body: `[Résolution] ${resolutionNote.trim()}`,
          is_public: false,
        });
      }
      return resolveRequest(id);
    },
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "resolved" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande marquée comme résolue.");
      setShowResolveForm(false);
      setResolutionNote("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible de résoudre la demande.");
    },
    onSettled: () => invalidate(),
  });

  const assignMut = useMutation({
    mutationFn: (assigneeId: string) => assignRequest(id, assigneeId),
    onMutate: async (assigneeId) => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, assigneeId, status: "in_progress" } : old,
      );
      return { previous };
    },
    onSuccess: (_, assigneeId) => {
      const agent = agentPool.find((u) => u.id === assigneeId);
      toast.success(`Réassigné à ${agent?.name ?? assigneeId}`);
      setShowReassign(false);
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible de réassigner la demande.");
    },
    onSettled: () => invalidate(),
  });

  const { data: workflows = [] } = useQuery({
    queryKey: ["request", id, "workflows"],
    queryFn: () => fetchRequestWorkflows(id),
    enabled: !isRequesterView,
    staleTime: 30_000,
  });

  const activeWorkflow = workflows.find((w) => w.workflowStatus === "active") ?? workflows[0];

  const { data: workflowDetails = [] } = useQuery({
    queryKey: ["workflow", activeWorkflow?.id, "details"],
    queryFn: () => fetchWorkflowDetails(activeWorkflow!.id),
    enabled: !isRequesterView && !!activeWorkflow,
    staleTime: 30_000,
  });

  const { data: tasksData } = useQuery({
    queryKey: ["request", id, "tasks"],
    queryFn: () => fetchRequestTasks(id),
    enabled: !isRequesterView,
    staleTime: 30_000,
  });
  const tasks = tasksData?.items ?? [];

  const createTaskMut = useMutation({
    mutationFn: (data: { task_type: "reassignment" | "reopening"; reason: string }) =>
      createTask({ task_type: data.task_type, request_id: id, reason: data.reason }),
    onSuccess: () => {
      toast.success("Tâche créée");
      setShowTaskForm(false);
      setTaskReason("");
      invalidateTasks();
    },
    onError: () => toast.error("Impossible de créer la tâche"),
  });

  const approveTaskMut = useMutation({
    mutationFn: (taskId: string) => approveTask(taskId),
    onSuccess: () => { toast.success("Tâche approuvée"); invalidateTasks(); },
    onError: () => toast.error("Impossible d'approuver la tâche"),
  });

  const rejectTaskMut = useMutation({
    mutationFn: (taskId: string) => rejectTask(taskId),
    onSuccess: () => { toast.success("Tâche rejetée"); invalidateTasks(); },
    onError: () => toast.error("Impossible de rejeter la tâche"),
  });

  const cancelTaskMut = useMutation({
    mutationFn: (taskId: string) => cancelTask(taskId),
    onSuccess: () => { toast.success("Tâche annulée"); invalidateTasks(); },
    onError: () => toast.error("Impossible d'annuler la tâche"),
  });

  // Phase 1 : utilisateur demande la réouverture (motif obligatoire)
  const requestReopenMut = useMutation({
    mutationFn: (reason: string) => requestReopen(id, reason),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, infos: { ...(old.infos ?? {}), reopen_requested: true } } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande de réouverture envoyée — le chef de service sera notifié.");
      setShowReopenForm(false);
      setReopenReason("");
    },
    onError: (err: unknown, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      const msg = (err as { message?: string })?.message;
      toast.error(msg ?? "Impossible d'envoyer la demande de réouverture.");
    },
    onSettled: () => invalidate(),
  });

  const closeMut = useMutation({
    mutationFn: () => closeRequest(id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "closed" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande clôturée — merci pour votre retour.");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible de clôturer la demande.");
    },
    onSettled: () => invalidate(),
  });

  const editMut = useMutation({
    mutationFn: () => requesterEditRequest(id, {
      title: editTitle.trim() || undefined,
      description: editDescription.trim() || undefined,
      category: editCategory || undefined,
      priority: editPriority || undefined,
      direction_id: editDirectionId || undefined,
      unit_id: editServiceId || undefined,
    }),
    onSuccess: () => {
      toast.success("Demande modifiée — re-routage effectué.");
      setShowEditForm(false);
      invalidate();
    },
    onError: (err: unknown) => {
      const msg = (err as { message?: string })?.message;
      toast.error(msg ?? "Impossible de modifier la demande.");
    },
  });

  const cancelMut = useMutation({
    mutationFn: () => cancelRequest(id, cancelReason.trim() || undefined),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "cancelled" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande annulée.");
      setShowCancelConfirm(false);
      setCancelReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible d'annuler la demande.");
    },
    onSettled: () => invalidate(),
  });

  const takeOwnershipMut = useMutation({
    mutationFn: () => updateRequest(id, { request_status: "in_progress" }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "in_progress" } : old,
      );
      return { previous };
    },
    onSuccess: () => { toast.success("Ticket pris en charge — traitement en cours."); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible de prendre en charge la demande.");
    },
    onSettled: () => invalidate(),
  });

  const requestInfoMut = useMutation({
    mutationFn: async () => {
      await createComment(id, {
        author_id: authorId,
        author_name: authorName,
        body: infoQuestion.trim(),
        is_public: true,
      });
      return updateRequest(id, { request_status: "pending" });
    },
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "pending" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Le demandeur a été notifié — ticket mis en attente.");
      setShowRequestInfoForm(false);
      setInfoQuestion("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible d'envoyer la demande d'informations.");
    },
    onSettled: () => invalidate(),
  });

  const resumeMut = useMutation({
    mutationFn: () => updateRequest(id, { request_status: "in_progress" }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "in_progress" } : old,
      );
      return { previous };
    },
    onSuccess: () => { toast.success("Traitement repris."); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible de reprendre le traitement.");
    },
    onSettled: () => invalidate(),
  });

  const changePriorityMut = useMutation({
    mutationFn: (priority: string) => updateRequest(id, { priority }),
    onMutate: async (priority) => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, priority: priority as RequestItem["priority"] } : old,
      );
      return { previous };
    },
    onSuccess: (_, p) => { toast.success(`Priorité changée → ${p}.`); setShowPriorityPicker(false); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible de changer la priorité.");
    },
    onSettled: () => invalidate(),
  });

  const rejectMut = useMutation({
    mutationFn: () => rejectTicket(id, rejectNote.trim() || "Rejetée par le responsable"),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "rejected" } : old,
      );
      return { previous };
    },
    onSuccess: () => { toast.success("Demande rejetée."); setShowRejectConfirm(false); setRejectNote(""); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible de rejeter la demande.");
    },
    onSettled: () => invalidate(),
  });

  const changeServiceMut = useMutation({
    mutationFn: (unit_id: string) => updateRequest(id, { unity_id: Number(unit_id) }),
    onSuccess: (_, s) => { toast.success(`Service changé → ${s}.`); setShowServicePicker(false); invalidate(); },
    onError: () => toast.error("Impossible de changer le service."),
  });

  const mergeMut = useMutation({
    mutationFn: () => mergeRequest(id, mergeTargetId.trim()),
    onSuccess: () => {
      toast.success("Demande fusionnée — la source est annulée.");
      setShowMergeDialog(false);
      setMergeTargetId("");
      invalidate();
    },
    onError: () => toast.error("Impossible de fusionner les demandes."),
  });

  const duplicateMut = useMutation({
    mutationFn: () => duplicateRequest(id),
    onSuccess: (newReq) => {
      toast.success(`Demande dupliquée — nouvelle référence : ${newReq.ref}`);
      invalidate();
    },
    onError: () => toast.error("Impossible de dupliquer la demande."),
  });

  const acceptStepMut = useMutation({
    mutationFn: ({ stepId, accepted, comment }: { stepId: string; accepted: boolean; comment?: string }) =>
      acceptWorkflowDetailById({ id: Number(stepId), accepted, comment }),
    onSuccess: (_, { accepted }) => {
      toast.success(accepted ? "Étape acceptée" : "Étape refusée");
      setAcceptingStepId(null);
      setAcceptComment("");
      invalidateWorkflows();
    },
    onError: () => toast.error("Impossible de mettre à jour l'étape workflow"),
  });

  const createCircuitMut = useMutation({
    mutationFn: () => createAutoCircuit(id, {
      direction_id: circuitDirectionId ? Number(circuitDirectionId) : undefined,
      unit_id: circuitUnitId ? Number(circuitUnitId) : undefined,
    }),
    onSuccess: () => {
      toast.success("Circuit de validation créé avec succès");
      setShowCircuitDialog(false);
      setCircuitDirectionId("");
      setCircuitUnitId("");
      invalidateWorkflows();
    },
    onError: () => toast.error("Impossible de créer le circuit de validation"),
  });

  const escalateMut = useMutation({
    mutationFn: () => escalateRequest(id, {
      level: escalateLevel,
      reason: escalateReason.trim() || "Escalade manuelle",
    }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, status: "escalated" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success(`Demande escaladée vers ${escalateLevel}.`);
      setShowEscalateForm(false);
      setEscalateReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible d'escalader la demande.");
    },
    onSettled: () => invalidate(),
  });

  const attachCommentMut = useMutation({
    mutationFn: (file: File) => uploadAttachment(id, file),
    onSuccess: () => {
      toast.success("Pièce jointe ajoutée au ticket.");
      if (attachRef.current) attachRef.current.value = "";
      invalidate();
    },
    onError: () => toast.error("Impossible d'ajouter la pièce jointe."),
  });

  const commentMut = useMutation({
    mutationFn: () =>
      createComment(id, {
        author_id: authorId,
        author_name: authorName,
        body: comment.trim(),
        is_public: isRequesterView ? true : isPublic,
      }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["request", id] });
      const previous = qc.getQueryData<RequestItem>(["request", id]);
      const optimisticComment = {
        id: `temp-${Date.now()}`,
        authorId: String(authorId),
        author: authorName,
        body: comment.trim(),
        isPublic: isRequesterView ? true : isPublic,
        isEdited: false,
        createdAt: new Date().toISOString(),
      };
      qc.setQueryData<RequestItem>(["request", id], (old) =>
        old ? { ...old, comments: [...(old.comments ?? []), optimisticComment] } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Commentaire ajouté");
      setComment("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["request", id], context.previous);
      toast.error("Impossible d'ajouter le commentaire.");
    },
    onSettled: () => invalidate(),
  });

  const { data: assigneeUser } = useQuery({
    queryKey: ["user", r?.assigneeId],
    queryFn: () => fetchUser(r!.assigneeId!),
    enabled: isRequesterView && !!r?.assigneeId,
    staleTime: 300_000,
  });

  const { data: agentsData } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchUsers({ role: "agent", limit: 100 }),
    enabled: !isRequesterView,
    staleTime: 120_000,
  });

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const { data: editUnits = [] } = useQuery({
    queryKey: ["units", editDirectionId],
    queryFn: () => fetchUnits(editDirectionId),
    enabled: !!editDirectionId && showEditForm,
    staleTime: 5 * 60_000,
  });

  const { data: units = [] } = useQuery({
    queryKey: ["units-all"],
    queryFn: () => fetchUnits(),
    enabled: !!r?.serviceId,
    staleTime: 5 * 60_000,
  });

  const { data: categoriesRef = [] } = useQuery({
    queryKey: ["ref-request-categories"],
    queryFn: fetchRequestCategories,
    staleTime: 10 * 60_000,
    enabled: isRequesterView,
  });
  const activeCategories = categoriesRef.filter((c) => c.status !== false);

  const escalationLevelsRef: { label: string }[] = [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Chargement…
      </div>
    );
  }

  if (isError || !r) {
    return (
      <div className="mx-auto max-w-md py-20 text-center">
        <h2 className="text-lg font-semibold">Demande introuvable</h2>
        <Button asChild variant="outline" className="mt-4 rounded-full">
          <Link to="/app/requests">Retour aux demandes</Link>
        </Button>
      </div>
    );
  }

  const localStatus = localAppreciation ? r.status : r.status;
  const authorType = (r.requesterType === "external" || r.isExternal) ? "external" : "internal";
  const slaPct = r.slaHours > 0 ? Math.min(100, Math.round((r.slaElapsed / r.slaHours) * 100)) : 0;
  const slaOver = r.slaHours > 0 && r.slaElapsed > r.slaHours;
  const assignedUnit = units.find((u) => String(u.id) === String(r.serviceId));
  const unitName = assignedUnit?.name ?? "—";
  const directionName = directions.find(
    (d) => String(d.id) === (assignedUnit?.direction_id ?? r.directionId),
  )?.name ?? "—";

  const isFinal = (["resolved", "closed", "rejected"] as const).includes(
    r.status as "resolved" | "closed" | "rejected",
  );

  const agentPool = agentsData?.items ?? [];
  const availableServices = [...new Set(agentPool.map((a) => a.unit_id).filter((u): u is string => !!u))];

  const canEdit = isRequesterView && r.status === "new";
  const canCancel = isRequesterView && (r.status === "new" || r.status === "qualified");
  const visibleComments = isRequesterView ? r.comments.filter((c) => c.isPublic) : r.comments;
  const needsUserResponse = isRequesterView && r.status === "pending";

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 rounded-full">
          <Link to="/app/requests">
            <ArrowLeft className="mr-1 h-4 w-4" /> Toutes les demandes
          </Link>
        </Button>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <motion.div
            layoutId={`req-ref-${r.id}`}
            className="font-mono text-xs text-muted-foreground"
          >
            {r.ref}
          </motion.div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{r.title}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge status={r.status} />
            <PriorityBadge priority={r.priority} />
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
              {r.category}
            </span>
          </div>
        </div>

        {needsUserResponse && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3">
            <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                L'agent vous demande des informations complémentaires
              </p>
              <p className="mt-0.5 text-sm text-amber-600/80 dark:text-amber-400/70">
                Répondez via la section commentaires ci-dessous pour que le traitement de votre demande puisse reprendre.
              </p>
            </div>
          </div>
        )}

        {isRequesterView && (canEdit || canCancel) && (
          <div className="flex flex-wrap gap-2">
            {canEdit && (
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  setEditTitle(r.title);
                  setEditDescription(r.description);
                  setEditCategory(r.category ?? "");
                  setEditPriority(r.priority ?? "medium");
                  setEditDirectionId(r.directionId ?? "");
                  setEditServiceId(r.serviceId ?? "");
                  setShowEditForm(true);
                }}
              >
                <Pencil className="mr-1.5 h-4 w-4" /> Modifier
              </Button>
            )}
            {canCancel && (
              <Button
                variant="outline"
                className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60"
                onClick={() => setShowCancelConfirm(true)}
              >
                <Ban className="mr-1.5 h-4 w-4" /> Annuler la demande
              </Button>
            )}
          </div>
        )}

        {!isRequesterView && (
          isFinal ? (
            <div className="flex items-center gap-2 rounded-full border border-border/40 bg-muted/30 px-4 py-2 text-sm text-muted-foreground">
              <Lock className="h-3.5 w-3.5" />
              Ticket {r.status === "closed" ? "clôturé" : r.status === "rejected" ? "rejeté" : "résolu"} — aucune action disponible
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {/* C1/C9 — Prendre en charge : ASSIGNED, agent seulement */}
              {r.status === "assigned" && isAgentOnly && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => takeOwnershipMut.mutate()}
                  disabled={takeOwnershipMut.isPending}
                >
                  {takeOwnershipMut.isPending
                    ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    : <UserCheck className="mr-1 h-4 w-4" />}
                  Prendre en charge
                </Button>
              )}
              {/* C2 — Demander des informations : IN_PROGRESS, agent seulement */}
              {r.status === "in_progress" && isAgentOnly && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setShowRequestInfoForm((v) => !v)}
                >
                  <MessageSquareWarning className="mr-1 h-4 w-4" />
                  Demander des infos
                </Button>
              )}
              {/* C3 — Reprendre le traitement : PENDING, agent seulement */}
              {r.status === "pending" && isAgentOnly && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => resumeMut.mutate()}
                  disabled={resumeMut.isPending}
                >
                  {resumeMut.isPending
                    ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    : <RotateCcw className="mr-1 h-4 w-4" />}
                  Reprendre le traitement
                </Button>
              )}
              {/* C5 — Escalader : agent, chef, directeur, admin seulement (pas DG) */}
              {canManageStatus && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setShowEscalateForm((v) => !v)}
                >
                  <ArrowUpRight className="mr-1 h-4 w-4" /> Escalader
                </Button>
              )}
              {/* C6 — Réassigner : agent, chef, admin seulement (pas directeur ni DG) */}
              {canAssign && (
              <div className="relative">
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setShowReassign((v) => !v)}
                  disabled={assignMut.isPending}
                >
                  <UserCheck className="mr-1 h-4 w-4" />
                  Réassigner
                  <ChevronDown className="ml-1 h-3.5 w-3.5" />
                </Button>
                {showReassign && (
                  <div className="absolute right-0 top-10 z-30 min-w-48 rounded-xl border border-border/50 bg-card shadow-xl p-1.5">
                    <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                      Choisir un agent
                    </p>
                    {agentPool.length === 0 && (
                      <p className="px-3 py-2 text-xs text-muted-foreground">Chargement…</p>
                    )}
                    {agentPool.map((agent) => (
                      <button
                        key={agent.id}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-foreground/5"
                        onClick={() => assignMut.mutate(agent.id)}
                      >
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                          {agent.name.slice(0, 2).toUpperCase()}
                        </span>
                        {agent.name}
                        {agent.availability && (
                          <span className="ml-auto text-[10px] text-muted-foreground">{agent.availability}</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              )}
              {/* Fusionner + Dupliquer + Créer circuit : agent, chef, admin */}
              {canAssign && (
                <>
                  <Button
                    variant="outline"
                    className="rounded-full"
                    onClick={() => setShowMergeDialog(true)}
                  >
                    <GitMerge className="mr-1 h-4 w-4" /> Fusionner
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-full"
                    onClick={() => duplicateMut.mutate()}
                    disabled={duplicateMut.isPending}
                  >
                    {duplicateMut.isPending
                      ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                      : <Copy className="mr-1 h-4 w-4" />}
                    Dupliquer
                  </Button>
                  {workflows.length === 0 && (
                    <Button
                      variant="outline"
                      className="rounded-full"
                      onClick={() => setShowCircuitDialog(true)}
                    >
                      <GitBranch className="mr-1 h-4 w-4" /> Créer circuit
                    </Button>
                  )}
                </>
              )}
              {/* Chef + Director: Changer priorité */}
              {(isDirector || isChief) && (
                <div className="relative">
                  <Button variant="outline" className="rounded-full" onClick={() => setShowPriorityPicker((v) => !v)} disabled={changePriorityMut.isPending}>
                    <ChevronDown className="mr-1 h-4 w-4" /> Priorité
                  </Button>
                  {showPriorityPicker && (
                    <div className="absolute right-0 top-10 z-30 min-w-40 rounded-xl border border-border/50 bg-card shadow-xl p-1.5">
                      {(["low", "medium", "high", "critical"] as const).map((p) => (
                        <button key={p} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-foreground/5" onClick={() => changePriorityMut.mutate(p)}>
                          <PriorityBadge priority={p} />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {/* Director: Rejeter + Changer service */}
              {isDirector && (
                <>
                  <Button variant="outline" className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60" onClick={() => setShowRejectConfirm((v) => !v)}>
                    <Ban className="mr-1 h-4 w-4" /> Rejeter
                  </Button>
                  <div className="relative">
                    <Button variant="outline" className="rounded-full" onClick={() => setShowServicePicker((v) => !v)} disabled={changeServiceMut.isPending}>
                      <Building2 className="mr-1 h-4 w-4" /> Service
                    </Button>
                    {showServicePicker && (
                      <div className="absolute right-0 top-10 z-30 min-w-52 rounded-xl border border-border/50 bg-card shadow-xl p-1.5">
                        <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">Choisir un service</p>
                        {availableServices.length === 0 ? (
                          <p className="px-3 py-2 text-xs text-muted-foreground">Aucun service disponible</p>
                        ) : availableServices.map((svc) => (
                          <button key={svc} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs hover:bg-foreground/5" onClick={() => changeServiceMut.mutate(svc)}>
                            {svc}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
              {/* C4 — Marquer résolue : 1 clic direct */}
              {canManageStatus && (r.status === "in_progress" || r.status === "assigned") && (
                <Button
                  className="rounded-full gradient-primary"
                  disabled={resolveMut.isPending}
                  onClick={() => resolveMut.mutate()}
                >
                  {resolveMut.isPending
                    ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    : <CheckCircle2 className="mr-1 h-4 w-4" />}
                  Marquer résolue
                </Button>
              )}
            </div>
          )
        )}
      </header>

      {!isRequesterView && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Parcours d'escalade
            </h3>
          </div>
          <EscalationProgressBar
            steps={buildStepsFromStatus(r.status, {
              reopened: r.status === "in_progress" && r.timeline.length > 4,
            }).map((s, i) => ({
              ...s,
              date: r.timeline[i]?.at,
              actor: r.timeline[i]?.by,
              comment: r.timeline[i]?.label,
            }))}
          />
        </div>
      )}

      {isRequesterView && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Avancement de votre demande
          </h3>
          <EscalationProgressBar
            steps={buildRequesterStepsFromStatus(r.status, { rejected: r.status === "rejected" })}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">

          {/* P10 — Bandeau PENDING */}
          {isRequesterView && r.status === "pending" && (
            <GlassCard className="border-amber-500/30 bg-amber-500/5">
              <div className="flex items-start gap-3">
                <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-amber-600 dark:text-amber-400">
                    Votre retour est attendu
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    L'agent en charge de votre demande attend des informations complémentaires.
                    Répondez dès que possible pour débloquer le traitement.
                  </p>
                  <Button
                    size="sm"
                    className="mt-3 rounded-full gradient-primary"
                    onClick={() => {
                      commentRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                      commentRef.current?.focus();
                    }}
                  >
                    Répondre
                  </Button>
                </div>
              </div>
            </GlassCard>
          )}

          {/* P7 — Formulaire de modification (demandeur, status=new uniquement) */}
          {showEditForm && (
            <GlassCard className="border-primary/30 bg-primary/5">
              <h3 className="mb-1 font-semibold">Modifier la demande</h3>
              <p className="mb-4 text-xs text-muted-foreground">
                Si vous changez la catégorie, la demande sera automatiquement re-routée vers le service concerné.
              </p>
              <div className="space-y-3">
                <div>
                  <Label className="text-sm">Titre</Label>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label className="text-sm">Catégorie</Label>
                    <Select value={editCategory} onValueChange={setEditCategory}>
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue placeholder="Sélectionner une catégorie" />
                      </SelectTrigger>
                      <SelectContent>
                        {activeCategories.map((c) => (
                          <SelectItem key={c.code} value={c.code}>{c.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm">Priorité</Label>
                    <Select value={editPriority} onValueChange={setEditPriority}>
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue placeholder="Sélectionner une priorité" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">Basse</SelectItem>
                        <SelectItem value="medium">Moyenne</SelectItem>
                        <SelectItem value="high">Haute</SelectItem>
                        <SelectItem value="critical">Critique</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label className="text-sm">Direction destinataire</Label>
                    <Select
                      value={editDirectionId}
                      onValueChange={(v) => {
                        setEditDirectionId(v);
                        setEditServiceId("");
                      }}
                    >
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue placeholder="Sélectionner une direction" />
                      </SelectTrigger>
                      <SelectContent>
                        {directions.filter((d) => d.status).map((d) => (
                          <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm">Service destinataire</Label>
                    <Select
                      value={editServiceId}
                      onValueChange={setEditServiceId}
                      disabled={!editDirectionId || editUnits.filter((u) => u.status).length === 0}
                    >
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue
                          placeholder={
                            !editDirectionId
                              ? "Choisissez une direction"
                              : "Service optionnel"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {editUnits.filter((u) => u.status).map((u) => (
                          <SelectItem key={u.id} value={String(u.id)}>{u.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label className="text-sm">Description détaillée</Label>
                  <textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    rows={4}
                    className="mt-1.5 w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <Button size="sm" variant="ghost" className="rounded-full"
                    onClick={() => setShowEditForm(false)}>
                    Annuler
                  </Button>
                  <Button
                    size="sm"
                    className="rounded-full gradient-primary"
                    disabled={
                      !editTitle.trim() ||
                      !editCategory ||
                      !editPriority ||
                      !editDirectionId ||
                      editDescription.trim().length < 10 ||
                      editMut.isPending
                    }
                    onClick={() => editMut.mutate()}
                  >
                    {editMut.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-1.5 h-4 w-4" />}
                    Enregistrer &amp; re-router
                  </Button>
                </div>
              </div>
            </GlassCard>
          )}

          {/* P7 — Confirmation annulation */}
          {showCancelConfirm && (
            <GlassCard className="border-destructive/30 bg-destructive/5">
              <div className="flex items-start gap-3">
                <Ban className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                <div className="min-w-0 flex-1 space-y-3">
                  <h3 className="font-semibold text-destructive">Annuler cette demande ?</h3>
                  <p className="text-sm text-muted-foreground">
                    Cette action est irréversible. La demande sera marquée comme annulée et ne sera plus traitée.
                  </p>
                  <textarea
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    placeholder="Motif de l'annulation (optionnel)…"
                    rows={2}
                    className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-destructive/40"
                  />
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="ghost" className="rounded-full"
                      onClick={() => { setShowCancelConfirm(false); setCancelReason(""); }}>
                      Garder la demande
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      className="rounded-full"
                      disabled={cancelMut.isPending}
                      onClick={() => cancelMut.mutate()}
                    >
                      {cancelMut.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Ban className="mr-1.5 h-4 w-4" />}
                      Confirmer l'annulation
                    </Button>
                  </div>
                </div>
              </div>
            </GlassCard>
          )}

          {/* C2 — Formulaire demande d'informations */}
          {!isRequesterView && showRequestInfoForm && (
            <GlassCard className="border-amber-500/30 bg-amber-500/5">
              <div className="flex items-start gap-3">
                <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                <div className="min-w-0 flex-1 space-y-3">
                  <h3 className="font-semibold text-amber-600 dark:text-amber-400">
                    Demander des informations complémentaires
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Le demandeur recevra une notification. Le ticket passera en attente jusqu'à sa réponse.
                  </p>
                  <textarea
                    value={infoQuestion}
                    onChange={(e) => setInfoQuestion(e.target.value)}
                    placeholder="Posez votre question ou décrivez les informations manquantes…"
                    rows={3}
                    className="w-full resize-none rounded-xl border border-amber-500/30 bg-background/60 px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                  />
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="ghost" className="rounded-full"
                      onClick={() => { setShowRequestInfoForm(false); setInfoQuestion(""); }}>
                      Annuler
                    </Button>
                    <Button
                      size="sm"
                      className="rounded-full bg-amber-500 text-white hover:bg-amber-600"
                      disabled={!infoQuestion.trim() || requestInfoMut.isPending}
                      onClick={() => requestInfoMut.mutate()}
                    >
                      {requestInfoMut.isPending
                        ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                        : <MessageSquareWarning className="mr-1.5 h-4 w-4" />}
                      Envoyer la demande
                    </Button>
                  </div>
                </div>
              </div>
            </GlassCard>
          )}

          {/* C5 — Modal escalade */}
          {!isRequesterView && (
            <Dialog
              open={showEscalateForm}
              onOpenChange={(open) => {
                if (!open) { setShowEscalateForm(false); setEscalateReason(""); }
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-destructive">
                    <ArrowUpRight className="h-5 w-5" />
                    Escalader la demande
                  </DialogTitle>
                  <DialogDescription>
                    Transférez cette demande à un niveau hiérarchique supérieur.
                    Le motif sera enregistré dans l'historique.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Niveau cible</label>
                    <Select value={escalateLevel} onValueChange={setEscalateLevel}>
                      <SelectTrigger className="h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(escalationLevelsRef.length > 0
                          ? escalationLevelsRef.map((l) => l.label)
                          : DEFAULT_LEVELS.slice(3, 6)
                        ).map((l) => (
                          <SelectItem key={l} value={l}>{l}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      Motif <span className="text-destructive">*</span>
                    </label>
                    <textarea
                      value={escalateReason}
                      onChange={(e) => setEscalateReason(e.target.value)}
                      placeholder="Décrivez la raison de l'escalade…"
                      rows={3}
                      className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-destructive/40"
                    />
                  </div>
                </div>

                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => { setShowEscalateForm(false); setEscalateReason(""); }}
                  >
                    Annuler
                  </Button>
                  <Button
                    variant="destructive"
                    className="rounded-full"
                    disabled={!escalateReason.trim() || escalateMut.isPending}
                    onClick={() => escalateMut.mutate()}
                  >
                    {escalateMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <ArrowUpRight className="mr-1.5 h-4 w-4" />}
                    Confirmer l'escalade
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* Fusion ticket — Dialog */}
          {!isRequesterView && (
            <Dialog
              open={showMergeDialog}
              onOpenChange={(open) => {
                if (!open) { setShowMergeDialog(false); setMergeTargetId(""); }
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <GitMerge className="h-5 w-5 text-primary" />
                    Fusionner la demande
                  </DialogTitle>
                  <DialogDescription>
                    Cette demande (<span className="font-mono font-medium">{r?.ref}</span>) sera fusionnée dans la demande cible.
                    Elle sera marquée annulée et liée à la cible. Cette action est irréversible.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-3 py-2">
                  <label className="text-sm font-medium">
                    ID de la demande cible <span className="text-destructive">*</span>
                  </label>
                  <input
                    type="text"
                    value={mergeTargetId}
                    onChange={(e) => setMergeTargetId(e.target.value)}
                    placeholder="Ex : 42"
                    className="w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                  <p className="text-xs text-muted-foreground">
                    Entrez l'identifiant numérique de la demande qui absorbe cette demande.
                  </p>
                </div>

                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => { setShowMergeDialog(false); setMergeTargetId(""); }}
                  >
                    Annuler
                  </Button>
                  <Button
                    className="rounded-full gradient-primary"
                    disabled={!mergeTargetId.trim() || mergeMut.isPending}
                    onClick={() => mergeMut.mutate()}
                  >
                    {mergeMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <GitMerge className="mr-1.5 h-4 w-4" />}
                    Confirmer la fusion
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* Director — Confirmation rejet inline (1 clic) */}
          {isDirector && showRejectConfirm && (
            <div className="flex items-center gap-2 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
              <Ban className="h-4 w-4 shrink-0 text-destructive" />
              <span className="flex-1 font-medium text-destructive">Confirmer le rejet de cette demande ?</span>
              <Button size="sm" variant="ghost" className="h-7 rounded-full px-3 text-xs"
                onClick={() => setShowRejectConfirm(false)}>
                Annuler
              </Button>
              <Button size="sm" variant="destructive" className="h-7 rounded-full px-3 text-xs"
                disabled={rejectMut.isPending} onClick={() => rejectMut.mutate()}>
                {rejectMut.isPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
                Rejeter
              </Button>
            </div>
          )}


          <GlassCard>
            <h3 className="mb-2 font-semibold">Description</h3>
            <p className="text-sm text-muted-foreground">{r.description}</p>
          </GlassCard>

          <GlassCard>
            <h3 className="mb-4 font-semibold">Historique</h3>
            <WorkflowTimeline events={r.timeline} />
          </GlassCard>

          <GlassCard>
            <h3 className="mb-4 font-semibold">Commentaires</h3>
            {visibleComments.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucun commentaire pour l'instant.</p>
            )}
            <ul className="space-y-3">
              {visibleComments.map((c) => (
                <li
                  key={c.id}
                  className="rounded-2xl border border-border/50 bg-background/60 p-4"
                >
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      <strong className="text-foreground">{c.author}</strong> ·{" "}
                      {formatDistanceToNow(new Date(c.createdAt), { addSuffix: true, locale: fr })}
                    </span>
                    {!isRequesterView && (
                      c.isPublic ? (
                        <span className="rounded-full bg-info/15 px-2 py-0.5 text-[10px] text-info">
                          Visible public
                        </span>
                      ) : (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px]">Interne</span>
                      )
                    )}
                  </div>
                  <p className="mt-2 text-sm">{c.body}</p>
                </li>
              ))}
            </ul>

            {r.status === "closed" || r.status === "rejected" ? (
              <div className="mt-5 flex items-center gap-2 rounded-xl border border-border/30 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                <Lock className="h-3.5 w-3.5 shrink-0" />
                Les commentaires sont désactivés — ticket {r.status === "closed" ? "clôturé" : "rejeté"}.
              </div>
            ) : (
              <div className="mt-5 space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                <Textarea
                  ref={commentRef}
                  placeholder={isRequesterView ? "Ajouter une réponse ou un commentaire…" : "Ajouter un commentaire…"}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  className="min-h-24"
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {!isRequesterView ? (
                    <div className="flex items-center gap-2">
                      <Switch id="public" checked={isPublic} onCheckedChange={setIsPublic} />
                      <Label htmlFor="public" className="text-sm">
                        Visible par le demandeur
                      </Label>
                    </div>
                  ) : <div />}
                  <div className="flex gap-2">
                    <input
                      ref={attachRef}
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.heic,.pdf"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) attachCommentMut.mutate(f);
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="rounded-full"
                      disabled={attachCommentMut.isPending}
                      onClick={() => attachRef.current?.click()}
                    >
                      {attachCommentMut.isPending
                        ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                        : <Paperclip className="mr-1 h-4 w-4" />}
                      Joindre
                    </Button>
                    <Button
                      size="sm"
                      className="rounded-full gradient-primary"
                      disabled={!comment.trim() || commentMut.isPending}
                      onClick={() => commentMut.mutate()}
                    >
                      {commentMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Publier"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </GlassCard>


          {/* ── Panneau rejet (demandeur uniquement) ── */}
          {isRequesterView && r.status === "rejected" && (
            <GlassCard className="space-y-4 border-destructive/30 bg-destructive/5">
              <div className="flex items-start gap-3">
                <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-destructive">Demande rejetée</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Votre demande a été examinée et n'a pas pu être traitée dans son état actuel.
                    Consultez l'historique ci-dessus pour connaître le motif précis du rejet.
                  </p>
                  {/* Dernier événement du timeline = motif du rejet */}
                  {r.timeline.length > 0 && (
                    <div className="mt-3 rounded-xl border border-destructive/20 bg-background/50 px-4 py-3 text-sm">
                      <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Motif
                      </span>
                      <p className="mt-1 text-foreground">
                        {r.timeline[r.timeline.length - 1].label}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="border-t border-border/30 pt-4 space-y-3">
                <p className="text-xs text-muted-foreground">
                  Si votre situation a évolué ou si vous pensez que ce rejet est injustifié,
                  vous pouvez réouvrir cette demande. L'historique complet sera conservé.
                </p>

                {!showReopenForm ? (
                  <Button
                    variant="outline"
                    className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60"
                    onClick={() => setShowReopenForm(true)}
                  >
                    <RotateCcw className="mr-1.5 h-4 w-4" />
                    Réouvrir la demande
                  </Button>
                ) : (
                  <div className="space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                    <p className="text-sm font-medium">
                      Motif de la réouverture <span className="text-destructive">*</span>
                    </p>
                    <textarea
                      value={reopenReason}
                      onChange={(e) => setReopenReason(e.target.value)}
                      placeholder="Décrivez ce qui a changé ou pourquoi vous contestez le rejet…"
                      rows={3}
                      className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="rounded-full"
                        onClick={() => { setShowReopenForm(false); setReopenReason(""); }}
                      >
                        Annuler
                      </Button>
                      <Button
                        size="sm"
                        className="rounded-full gradient-primary"
                        disabled={requestReopenMut.isPending || !reopenReason.trim()}
                        onClick={() => requestReopenMut.mutate(reopenReason.trim())}
                      >
                        {requestReopenMut.isPending
                          ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                          : <RotateCcw className="mr-1.5 h-4 w-4" />
                        }
                        Demander la réouverture
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </GlassCard>
          )}

          {isRequesterView && r.status === "resolved" && (
            <GlassCard className={
              (r.infos as Record<string, unknown>)?.reopen_requested
                ? "border-warning/30 bg-warning/5"
                : "border-success/30 bg-success/5"
            }>
              <div className="flex items-start gap-3">
                {(r.infos as Record<string, unknown>)?.reopen_requested
                  ? <RotateCcw className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                  : <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                }
                <div className="min-w-0 flex-1 space-y-3">
                  {(r.infos as Record<string, unknown>)?.reopen_requested ? (
                    /* Réouverture déjà demandée — en attente chef */
                    <div>
                      <h3 className="font-semibold text-warning">Réouverture en attente d'approbation</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Votre demande de réouverture a été transmise au chef de service.
                        Vous serez notifié dès qu'une décision sera prise.
                      </p>
                    </div>
                  ) : (
                    <>
                      <div>
                        <h3 className="font-semibold text-success">Demande résolue</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          L'agent a marqué votre demande comme résolue. Confirmez si le problème est
                          bien réglé, ou contestez la résolution en précisant le motif.
                        </p>
                      </div>
                      {!showReopenForm ? (
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            className="rounded-full"
                            disabled={closeMut.isPending}
                            onClick={() => closeMut.mutate()}
                          >
                            {closeMut.isPending
                              ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              : <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />}
                            Confirmer la résolution
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10"
                            onClick={() => setShowReopenForm(true)}
                          >
                            <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                            Le problème persiste — contester
                          </Button>
                        </div>
                      ) : (
                        <div className="space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                          <div>
                            <p className="text-sm font-medium">
                              Motif de contestation <span className="text-destructive">*</span>
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              Obligatoire — décrivez précisément ce qui n'a pas été résolu.
                            </p>
                          </div>
                          <textarea
                            value={reopenReason}
                            onChange={(e) => setReopenReason(e.target.value)}
                            placeholder="Ex : La panne a repris le lendemain, le problème n'est pas résolu…"
                            rows={3}
                            className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                          />
                          <div className="flex justify-end gap-2">
                            <Button size="sm" variant="ghost" className="rounded-full"
                              onClick={() => { setShowReopenForm(false); setReopenReason(""); }}>
                              Annuler
                            </Button>
                            <Button
                              size="sm"
                              className="rounded-full gradient-primary"
                              disabled={requestReopenMut.isPending || !reopenReason.trim()}
                              onClick={() => requestReopenMut.mutate(reopenReason.trim())}
                            >
                              {requestReopenMut.isPending
                                ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                : <RotateCcw className="mr-1.5 h-3.5 w-3.5" />}
                              Demander la réouverture
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </GlassCard>
          )}

          {isRequesterView && (r.status === "resolved" || r.status === "closed") && (
            <div>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Votre avis
              </h3>
              <AppreciationForm
                requestId={r.id}
                authorType={authorType}
                existing={localAppreciation ?? r.appreciation}
                isClosed={r.status === "closed"}
                onSubmit={(appr) => {
                  setLocalAppreciation(appr);
                  invalidate();
                }}
                onReopen={() => {
                  toast.success("Demande rouverte — un agent va la reprendre en charge.");
                  invalidate();
                }}
                onSave={async (data) => {
                  const hasExisting = !!(localAppreciation ?? r.appreciation);
                  if (hasExisting) {
                    await updateRequestAppreciation(r.id, data);
                  } else {
                    await submitAppreciation(r.id, data);
                  }
                }}
              />
            </div>
          )}

          {!isRequesterView && workflowDetails.length > 0 && (
            <GlassCard>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                <ListTodo className="h-4 w-4" />
                Étapes du workflow
              </h3>
              <div className="space-y-2">
                {workflowDetails.map((step: WorkflowDetailItem) => {
                  const isChild = !!step.parentId;
                  return (
                    <div
                      key={step.id}
                      className={
                        "rounded-xl border border-border/40 bg-background/40 px-3 py-2.5 text-sm " +
                        (isChild ? "ml-6" : "")
                      }
                    >
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex shrink-0 flex-col gap-1">
                          <span
                            className={
                              "inline-block h-2 w-2 rounded-full " +
                              (step.activated
                                ? "bg-primary"
                                : step.accepted
                                ? "bg-success"
                                : "bg-muted-foreground/40")
                            }
                          />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-muted/60 px-2 py-0.5 text-xs font-mono text-muted-foreground">
                              {step.workflowStatus}
                            </span>
                            {step.accepted && (
                              <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">
                                Accepté
                              </span>
                            )}
                            {step.activated && (
                              <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
                                Actif
                              </span>
                            )}
                          </div>
                          {(step.unitId || step.agentId) && (
                            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                              {step.unitId && (
                                <span className="flex items-center gap-1">
                                  <Building2 className="h-3 w-3" />
                                  Unité {step.unitId}
                                </span>
                              )}
                              {step.agentId && (
                                <span className="flex items-center gap-1">
                                  <User className="h-3 w-3" />
                                  Agent {step.agentId}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        {/* Accepter / Refuser : uniquement sur les étapes actives non encore acceptées */}
                        {step.activated && !step.accepted && canAssign && (
                          <div className="flex shrink-0 gap-1.5">
                            <Button
                              size="sm"
                              className="h-7 rounded-full px-3 text-xs"
                              onClick={() => {
                                setAcceptingStepId(step.id);
                                setAcceptDialogMode("accept");
                                setAcceptComment("");
                              }}
                            >
                              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                              Accepter
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-full px-3 text-xs text-destructive hover:bg-destructive/10 border-destructive/40"
                              onClick={() => {
                                setAcceptingStepId(step.id);
                                setAcceptDialogMode("refuse");
                                setAcceptComment("");
                              }}
                            >
                              <X className="mr-1 h-3.5 w-3.5" />
                              Refuser
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          )}

          {/* Dialog — Accepter / Refuser une étape workflow */}
          {acceptingStepId && (
            <Dialog
              open
              onOpenChange={(open) => { if (!open) { setAcceptingStepId(null); setAcceptComment(""); } }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className={`flex items-center gap-2 ${acceptDialogMode === "accept" ? "text-success" : "text-destructive"}`}>
                    {acceptDialogMode === "accept"
                      ? <><CheckCircle2 className="h-5 w-5" /> Accepter l'étape</>
                      : <><X className="h-5 w-5" /> Refuser l'étape</>
                    }
                  </DialogTitle>
                  <DialogDescription>
                    {acceptDialogMode === "accept"
                      ? "Confirmez l'acceptation de cette étape du circuit de validation."
                      : "Cette étape sera marquée comme refusée. Un commentaire est recommandé."}
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-3 py-2">
                  <label className="text-sm font-medium">
                    Commentaire {acceptDialogMode === "refuse" && <span className="text-destructive">*</span>}
                    {acceptDialogMode === "accept" && <span className="text-muted-foreground"> (optionnel)</span>}
                  </label>
                  <textarea
                    value={acceptComment}
                    onChange={(e) => setAcceptComment(e.target.value)}
                    placeholder={acceptDialogMode === "accept" ? "Note sur la validation…" : "Motif du refus…"}
                    rows={3}
                    className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>
                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => { setAcceptingStepId(null); setAcceptComment(""); }}
                  >
                    Annuler
                  </Button>
                  <Button
                    className={`rounded-full ${acceptDialogMode === "accept" ? "gradient-primary" : "bg-destructive text-destructive-foreground hover:bg-destructive/90"}`}
                    disabled={(acceptDialogMode === "refuse" && !acceptComment.trim()) || acceptStepMut.isPending}
                    onClick={() => acceptStepMut.mutate({
                      stepId: acceptingStepId,
                      accepted: acceptDialogMode === "accept",
                      comment: acceptComment.trim() || undefined,
                    })}
                  >
                    {acceptStepMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : acceptDialogMode === "accept"
                        ? <><CheckCircle2 className="mr-1.5 h-4 w-4" /> Confirmer l'acceptation</>
                        : <><X className="mr-1.5 h-4 w-4" /> Confirmer le refus</>
                    }
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* Dialog — Créer circuit de validation */}
          {!isRequesterView && (
            <Dialog
              open={showCircuitDialog}
              onOpenChange={(open) => { if (!open) { setShowCircuitDialog(false); setCircuitDirectionId(""); setCircuitUnitId(""); } }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <GitBranch className="h-5 w-5 text-primary" />
                    Créer un circuit de validation
                  </DialogTitle>
                  <DialogDescription>
                    Un circuit de validation automatique sera créé pour cette demande.
                    Laissez les champs vides pour utiliser la configuration par défaut.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      Direction cible <span className="text-muted-foreground">(optionnel)</span>
                    </label>
                    <select
                      value={circuitDirectionId}
                      onChange={(e) => setCircuitDirectionId(e.target.value)}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <option value="">Configuration automatique</option>
                      {directions.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      Service cible <span className="text-muted-foreground">(optionnel)</span>
                    </label>
                    <select
                      value={circuitUnitId}
                      onChange={(e) => setCircuitUnitId(e.target.value)}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <option value="">Configuration automatique</option>
                      {units
                        .filter((u) => !circuitDirectionId || u.direction_id === circuitDirectionId)
                        .map((u) => (
                          <option key={u.id} value={u.id}>{u.name}</option>
                        ))}
                    </select>
                  </div>
                </div>
                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => { setShowCircuitDialog(false); setCircuitDirectionId(""); setCircuitUnitId(""); }}
                  >
                    Annuler
                  </Button>
                  <Button
                    className="rounded-full gradient-primary"
                    disabled={createCircuitMut.isPending}
                    onClick={() => createCircuitMut.mutate()}
                  >
                    {createCircuitMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <><GitBranch className="mr-1.5 h-4 w-4" /> Créer le circuit</>
                    }
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>

        <aside className="space-y-4">
          <GlassCard>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Suivi SLA
            </h3>
            <div className="flex items-end justify-between">
              <div className="text-3xl font-bold">{slaPct}%</div>
              <span
                className={
                  "rounded-full px-2.5 py-0.5 text-xs font-medium " +
                  (slaOver
                    ? "bg-destructive/15 text-destructive"
                    : "bg-success/15 text-success")
                }
              >
                {slaOver ? "Dépassé" : "Dans les temps"}
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={"h-full rounded-full " + (slaOver ? "bg-destructive" : "gradient-primary")}
                style={{ width: slaPct + "%" }}
              />
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              {r.slaHours > 0
                ? `${r.slaElapsed}h écoulées / ${r.slaHours}h`
                : "SLA non configuré"}
            </div>
          </GlassCard>

          {!isRequesterView && <RequesterCard r={r} directions={directions} />}

          <GlassCard>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Traitement
            </h3>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Direction</dt>
                <dd className="mt-0.5">{directionName}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Service</dt>
                <dd className="mt-0.5">{unitName}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Catégorie</dt>
                <dd className="mt-0.5">{r.category}</dd>
              </div>
              {isRequesterView && r.assigneeId && (
                <div>
                  <dt className="text-xs text-muted-foreground">Agent en charge</dt>
                  <dd className="mt-0.5 flex items-center gap-1.5">
                    <UserCheck className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    {assigneeUser?.name ?? "En cours d'assignation"}
                  </dd>
                </div>
              )}
              {isRequesterView && !r.assigneeId && !isFinal && (
                <div>
                  <dt className="text-xs text-muted-foreground">Agent en charge</dt>
                  <dd className="mt-0.5 text-muted-foreground italic">En attente d'assignation</dd>
                </div>
              )}
            </dl>
          </GlassCard>

          {slaOver && (
            <GlassCard className="border-destructive/40 bg-destructive/5">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 text-destructive" />
                <div>
                  <div className="font-semibold text-destructive">SLA dépassé</div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Cette demande nécessite une attention immédiate ou une escalade.
                  </p>
                </div>
              </div>
            </GlassCard>
          )}
        </aside>
      </div>
    </div>
  );
}

function RequesterCard({ r: req, directions }: { r: RequestItem; directions: Direction[] }) {
  const [role] = useRole();
  const isAgent = role !== "user";
  const isInternal = req.requesterType === "internal" || !req.isExternal;
  const isExternal = req.requesterType === "external" || req.isExternal;

  return (
    <GlassCard>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        Fiche demandeur
      </h3>

      <div className="mb-3 flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">
          {req.requesterName.split(" ").map((p: string) => p[0]).join("").slice(0, 2)}
        </span>
        <div className="min-w-0">
          <div className="font-semibold leading-none">{req.requesterName}</div>
          <div className="mt-0.5 flex items-center gap-1.5">
            {isInternal ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                <BadgeCheck className="h-3 w-3" /> Employé EDG
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent-foreground dark:text-accent">
                <Users className="h-3 w-3" /> Client externe / citoyen
              </span>
            )}
          </div>
        </div>
      </div>

      <dl className="space-y-2.5 text-sm">
        {req.requesterPhone && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Phone className="h-3.5 w-3.5 shrink-0" />
            <a href={`tel:${req.requesterPhone}`} className="hover:text-foreground">
              {req.requesterPhone}
            </a>
          </div>
        )}
        {req.requesterEmail && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Mail className="h-3.5 w-3.5 shrink-0" />
            <a href={`mailto:${req.requesterEmail}`} className="truncate hover:text-foreground">
              {req.requesterEmail}
            </a>
          </div>
        )}
        {req.requesterAddress && (
          <div className="flex items-start gap-2 text-muted-foreground">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{req.requesterAddress}</span>
          </div>
        )}

        {isInternal && req.employeeMatricule && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-primary" />
            <span>Matricule : <span className="font-mono font-medium text-foreground">{req.employeeMatricule}</span></span>
          </div>
        )}
        {isInternal && req.requesterJob && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <User className="h-3.5 w-3.5 shrink-0" />
            <span>{req.requesterJob}</span>
          </div>
        )}
        {isInternal && req.requesterDirectionId && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Building2 className="h-3.5 w-3.5 shrink-0" />
            <span>{directions.find((d) => String(d.id) === String(req.requesterDirectionId))?.name ?? req.requesterDirectionId}</span>
          </div>
        )}

        {isExternal && req.meterNumber && (
          <div className="text-xs font-mono text-muted-foreground">
            Compteur : <span className="font-medium text-foreground">{req.meterNumber}</span>
          </div>
        )}
        {isExternal && req.clientRef && (
          <div className="text-xs font-mono text-muted-foreground">
            Réf. client : <span className="font-medium text-foreground">{req.clientRef}</span>
          </div>
        )}
        {isExternal && req.siteType && (
          <div className="text-xs text-muted-foreground">
            Site :{" "}
            <span className="font-medium text-foreground">
              {req.siteType === "domicile" ? "Domicile"
                : req.siteType === "commerce" ? "Commerce / entreprise"
                : "Administration / école"}
            </span>
          </div>
        )}

        {isExternal && isAgent && (req.lat != null || req.locationLabel) && (
          <div className="mt-1 rounded-xl border border-primary/20 bg-primary/5 p-2.5">
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
              <MapPin className="h-3 w-3" /> Localisation GPS (confidentiel)
            </div>
            {req.locationLabel && (
              <div className="text-xs text-foreground">{req.locationLabel}</div>
            )}
            {req.lat != null && req.lng != null && (
              <div className="mt-0.5 font-mono text-[10px] text-muted-foreground/70">
                {req.lat.toFixed(5)}, {req.lng.toFixed(5)}
              </div>
            )}
          </div>
        )}
      </dl>
    </GlassCard>
  );
}
