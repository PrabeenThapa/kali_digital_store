"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  LayoutDashboard,
  Users,
  Package,
  ShoppingCart,
  CreditCard,
  ShieldCheck,
  Search,
  RefreshCw,
  TrendingUp,
  DollarSign,
  UserCheck,
  UserX,
  Copy,
  Check,
  ExternalLink,
  Lock,
  Unlock,
  Edit3,
  Eye,
  ArrowUpRight,
  ShieldAlert,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  Layers,
  Sun,
  Moon,
  Bolt,
  Plus,
  Trash2,
  Filter,
  Flame,
  Star,
  Award,
  Tag,
  Sliders,
  Percent,
  Key,
  Globe,
  QrCode,
  AlertTriangle,
  Info,
  CheckCheck,
  X,
  ChevronRight,
  TrendingDown,
  ArrowDownUp,
  Wallet,
  Upload,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileText,
  Crown
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
// Types & Interfaces
// ─────────────────────────────────────────────────────────────────────────────

interface AdminStats {
  total_users: number;
  new_users_today: number;
  total_sales_usd: number;
  sales_today_usd: number;
  total_profit_usd: number;
  total_orders: number;
  orders_today: number;
  total_products: number;
  in_stock_products: number;
  pending_payments: number;
  succeeded_payments_volume: number;
}

interface AdminProduct {
  id: string; // "local_1" or "reseller_5"
  raw_id: number;
  name: string;
  description?: string;
  category_id: number;
  category_name: string;
  price: number;
  price_npr?: number | null;
  cost_price: number;
  stock: number;
  is_featured: boolean;
  is_hot: boolean;
  is_bestseller: boolean;
  badge_text: string | null;
  is_active: boolean;
  auto_delivery?: boolean;
  delivery_template?: string | null;
  delivery_type?: string;
  account_type?: string;
  warranty: string | null;
  note: string | null;
  source_type: "local" | "reseller";
  source_name: string | null;
}

interface AdminCategory {
  id: number;
  name: string;
  is_active: boolean;
  products_count: number;
}

interface AdminUser {
  telegram_id: number;
  email: string | null;
  balance: number;
  role_name: string;
  role_id: number;
  registration_date: string;
  is_blocked: boolean;
  discount_percent: number;
  purchases_count: number;
  total_spent: number;
}

interface UserPurchaseItem {
  id: number;
  unique_id: number;
  item_name: string;
  price: number;
  cost_price: number;
  profit: number;
  bought_datetime: string;
  value: string;
  source_type: string;
  status: string;
}

interface ResellerSourceBalance {
  id: number;
  name: string;
  balance: number;
  currency: string;
  is_active: boolean;
  last_synced: string | null;
}

interface ResellerTopUpLog {
  id: number;
  source_id: number;
  source_name: string;
  amount: number;
  currency: string;
  payment_method: string | null;
  note: string | null;
  tx_hash: string | null;
  created_at: string;
}

interface ResellerBudget {
  balances: ResellerSourceBalance[];
  total_balance_usd: number;
  total_spent_usd: number;
  total_loaded_usd: number;
  orders_count: number;
  topups: ResellerTopUpLog[];
}

interface AdminOrder {
  id: number;
  unique_id: number;
  buyer_id: number | null;
  buyer_email: string | null;
  item_name: string;
  price: number;
  cost_price: number;
  profit: number;
  bought_datetime: string;
  value: string;
}

interface AdminPayment {
  id: number;
  provider: string;
  external_id: string;
  user_id: number | null;
  user_email?: string | null;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
}

interface PendingNepalPayment {
  id: number;
  payment_id: number;
  tx_id: string;
  user_id: number | null;
  user_email: string | null;
  amount_usd: number;
  amount_npr: number;
  note: string | null;
  proof_image: string | null;
  created_at: string;
  status: string;
}

interface AdminPromo {
  id: number;
  code: string;
  discount_type: string;
  discount_value: number;
  max_uses: number;
  current_uses: number;
  is_active: boolean;
  created_at: string;
}

interface StoreSettings {
  geo_filtering_enabled: boolean;
  npr_exchange_rate: number;
  nepal_qr_url: string;
  nepal_qr_title: string;
  nepal_qr_account_name: string;
  nepal_qr_account_id: string;
  nepal_qr_instructions: string;
  nepal_coming_soon: boolean;
  nepal_coming_soon_text: string;
  mantra_bar_text: string;
  hero_title: string;
  hero_subtitle: string;
  announcement_banner_enabled: boolean;
  announcement_banner_text: string;
  announcement_banner_type: string;
  global_auto_delivery_enabled?: boolean;
  global_delivery_template?: string;
}

type TabType = "overview" | "products" | "categories" | "payments" | "orders" | "users" | "budget" | "promocodes" | "settings";

export default function AdminPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Core data states
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [payments, setPayments] = useState<AdminPayment[]>([]);
  const [pendingNepal, setPendingNepal] = useState<PendingNepalPayment[]>([]);
  const [promocodes, setPromocodes] = useState<AdminPromo[]>([]);
  const [settings, setSettings] = useState<StoreSettings>({
    geo_filtering_enabled: true,
    npr_exchange_rate: 135.0,
    nepal_qr_url: "",
    nepal_qr_title: "eSewa / Khalti / Fonepay Direct QR",
    nepal_qr_account_name: "Kali Store Nepal",
    nepal_qr_account_id: "9800000000",
    nepal_qr_instructions: "",
    nepal_coming_soon: false,
    nepal_coming_soon_text: "",
    mantra_bar_text: "॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥",
    hero_title: "KALI DIGITAL STORE",
    hero_subtitle: "Genuine ChatGPT Plus, Claude, Gemini, Canva Pro, JetBrains, VPNs, and Dev API tokens with instant cryptographic delivery and eternal warranty.",
    announcement_banner_enabled: false,
    announcement_banner_text: "",
    announcement_banner_type: "info",
    global_auto_delivery_enabled: true,
    global_delivery_template: "Hello {customer_email},\n\nThank you for your order! Here are your digital credentials:\n\n{credentials}\n\nProduct: {product_name} (x{quantity})\nWarranty: {warranty}\nSupport Contact: {support_contact}",
  });

  // User Sorting & Purchases state
  const [userSortField, setUserSortField] = useState<"balance" | "purchases_count" | "total_spent" | "registration_date" | "telegram_id">("registration_date");
  const [userSortOrder, setUserSortOrder] = useState<"asc" | "desc">("desc");
  const [isUserPurchasesOpen, setIsUserPurchasesOpen] = useState(false);
  const [userPurchasesUser, setUserPurchasesUser] = useState<AdminUser | null>(null);
  const [userPurchasesList, setUserPurchasesList] = useState<UserPurchaseItem[]>([]);
  const [loadingUserPurchases, setLoadingUserPurchases] = useState(false);

  // Reseller Budget & API Wallets state
  const [resellerBudget, setResellerBudget] = useState<ResellerBudget | null>(null);
  const [budgetPeriod, setBudgetPeriod] = useState<"all" | "day" | "week" | "month" | "custom">("all");
  const [budgetStartDate, setBudgetStartDate] = useState("");
  const [budgetEndDate, setBudgetEndDate] = useState("");
  const [isTopUpModalOpen, setIsTopUpModalOpen] = useState(false);
  const [topUpSourceId, setTopUpSourceId] = useState<number>(0);
  const [topUpAmount, setTopUpAmount] = useState("");
  const [topUpMethod, setTopUpMethod] = useState("USDT TRC20");
  const [topUpNote, setTopUpNote] = useState("");
  const [topUpTxHash, setTopUpTxHash] = useState("");

  // QR Upload & Banner Preview state
  const [isUploadingQr, setIsUploadingQr] = useState(false);
  const [isBannerPreviewOpen, setIsBannerPreviewOpen] = useState(false);

  // Product Filters
  const [prodSearch, setProdSearch] = useState("");
  const [prodCatFilter, setProdCatFilter] = useState<string>("all");
  const [prodStatusFilter, setProdStatusFilter] = useState<"all" | "active" | "disabled">("all");
  const [prodStockFilter, setProdStockFilter] = useState<"all" | "instock" | "lowstock" | "outofstock">("all");
  const [prodBadgeFilter, setProdBadgeFilter] = useState<"all" | "featured" | "hot" | "bestseller">("all");
  const [prodSourceFilter, setProdSourceFilter] = useState<"all" | "local" | "reseller">("all");

  // Modals state
  const [isAddProductOpen, setIsAddProductOpen] = useState(false);
  const [isEditProductOpen, setIsEditProductOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null);
  const [isBulkPriceOpen, setIsBulkPriceOpen] = useState(false);
  const [isStockModalOpen, setIsStockModalOpen] = useState(false);
  const [stockProduct, setStockProduct] = useState<AdminProduct | null>(null);
  const [stockItems, setStockItems] = useState<{ id: number; value: string; is_infinity: boolean }[]>([]);
  const [newStockKeys, setNewStockKeys] = useState("");
  const [isAddCategoryOpen, setIsAddCategoryOpen] = useState(false);
  const [isEditCategoryOpen, setIsEditCategoryOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<AdminCategory | null>(null);
  const [isBalanceModalOpen, setIsBalanceModalOpen] = useState(false);
  const [balanceUser, setBalanceUser] = useState<AdminUser | null>(null);
  const [balanceAmount, setBalanceAmount] = useState("");
  const [balanceReason, setBalanceReason] = useState("Admin balance adjustment");
  const [isProofModalOpen, setIsProofModalOpen] = useState(false);
  const [selectedProofImg, setSelectedProofImg] = useState<string | null>(null);
  const [isOrderCredentialsOpen, setIsOrderCredentialsOpen] = useState(false);
  const [selectedOrderCredentials, setSelectedOrderCredentials] = useState<string | null>(null);

  // Form states for Add Product
  const [newProdName, setNewProdName] = useState("");
  const [newProdCatId, setNewProdCatId] = useState<number>(0);
  const [newProdPrice, setNewProdPrice] = useState("");
  const [newProdPriceNpr, setNewProdPriceNpr] = useState("");
  const [newProdCostPrice, setNewProdCostPrice] = useState("");
  const [newProdWarranty, setNewProdWarranty] = useState("24 Hours");
  const [newProdNote, setNewProdNote] = useState("");
  const [newProdDesc, setNewProdDesc] = useState("");
  const [newProdFeatured, setNewProdFeatured] = useState(false);
  const [newProdHot, setNewProdHot] = useState(false);
  const [newProdBestseller, setNewProdBestseller] = useState(false);
  const [newProdBadgeText, setNewProdBadgeText] = useState("");
  const [newProdAutoDelivery, setNewProdAutoDelivery] = useState(true);
  const [newProdDeliveryType, setNewProdDeliveryType] = useState<string>("instant");
  const [newProdAccountType, setNewProdAccountType] = useState<string>("preactivated");
  const [newProdDeliveryTemplate, setNewProdDeliveryTemplate] = useState("");
  const [newProdInitialKeys, setNewProdInitialKeys] = useState("");

  // Bulk Price Form State
  const [bulkCatId, setBulkCatId] = useState<string>("all");
  const [bulkChangeType, setBulkChangeType] = useState<"percentage" | "fixed_amount">("percentage");
  const [bulkChangeValue, setBulkChangeValue] = useState("");
  const [bulkRounding, setBulkRounding] = useState<number>(0.25);

  // Category Form State
  const [newCatName, setNewCatName] = useState("");

  // Promocode Form State
  const [isAddPromoOpen, setIsAddPromoOpen] = useState(false);
  const [newPromoCode, setNewPromoCode] = useState("");
  const [newPromoType, setNewPromoType] = useState("percent");
  const [newPromoVal, setNewPromoVal] = useState("");
  const [newPromoMaxUses, setNewPromoMaxUses] = useState("0");

  // Inline price edit helper
  const [inlinePriceId, setInlinePriceId] = useState<string | null>(null);
  const [inlinePriceVal, setInlinePriceVal] = useState<string>("");

  const showToast = (text: string, type: "success" | "error" = "success") => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Data Loaders
  // ─────────────────────────────────────────────────────────────────────────

  // Auth Gate State
  const [needsAuth, setNeedsAuth] = useState(false);
  const [adminUsername, setAdminUsername] = useState("prabin");
  const [adminPassword, setAdminPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError("");
    try {
      const res = await api.post("/auth/admin_login", {
        username: adminUsername,
        password: adminPassword,
      });
      localStorage.setItem("token", res.data.access_token);
      setNeedsAuth(false);
      setAuthError("");
      loadAllData();
      showToast("⚡ Welcome back, Master Admin! Control Hub unlocked.");
    } catch (err: any) {
      setAuthError(err?.response?.data?.detail || "Invalid Admin username or password.");
    } finally {
      setAuthLoading(false);
    }
  };

  const loadAllData = useCallback(async () => {
    try {
      setRefreshing(true);
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      if (!token) {
        setNeedsAuth(true);
        setLoading(false);
        setRefreshing(false);
        return;
      }

      const [
        statsRes,
        prodRes,
        catRes,
        userRes,
        orderRes,
        pmtRes,
        nepalRes,
        promoRes,
        settingsRes,
        delivTplRes,
      ] = await Promise.allSettled([
        api.get("/admin/stats"),
        api.get("/admin/products?limit=500"),
        api.get("/admin/categories"),
        api.get("/admin/users?limit=100"),
        api.get("/admin/orders?limit=100"),
        api.get("/admin/payments?limit=100"),
        api.get("/admin/payments/pending-nepal"),
        api.get("/admin/promocodes"),
        api.get("/admin/settings"),
        api.get("/admin/settings/delivery-templates"),
      ]);

      let isUnauthorized = false;
      [statsRes, prodRes, catRes, userRes, orderRes, pmtRes, nepalRes, promoRes, settingsRes, delivTplRes].forEach(res => {
        if (res.status === "rejected" && (res.reason?.response?.status === 401 || res.reason?.response?.status === 403)) {
          isUnauthorized = true;
        }
      });

      if (isUnauthorized) {
        setNeedsAuth(true);
        setLoading(false);
        setRefreshing(false);
        return;
      }

      setNeedsAuth(false);
      if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
      if (prodRes.status === "fulfilled") setProducts(prodRes.value.data);
      if (catRes.status === "fulfilled") {
        setCategories(catRes.value.data);
        if (catRes.value.data.length > 0) {
          setNewProdCatId(prev => (prev === 0 ? catRes.value.data[0].id : prev));
        }
      }
      if (userRes.status === "fulfilled") setUsers(userRes.value.data);
      if (orderRes.status === "fulfilled") setOrders(orderRes.value.data);
      if (pmtRes.status === "fulfilled") setPayments(pmtRes.value.data);
      if (nepalRes.status === "fulfilled") setPendingNepal(nepalRes.value.data);
      if (promoRes.status === "fulfilled") setPromocodes(promoRes.value.data);
      if (settingsRes.status === "fulfilled") {
        setSettings(prev => ({ ...prev, ...settingsRes.value.data }));
      }
      if (delivTplRes.status === "fulfilled") {
        setSettings(prev => ({
          ...prev,
          global_auto_delivery_enabled: delivTplRes.value.data.global_auto_delivery_enabled,
          global_delivery_template: delivTplRes.value.data.global_delivery_template,
        }));
      }
    } catch (e: any) {
      if (e.response?.status === 401 || e.response?.status === 403) {
        setNeedsAuth(true);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial mount trigger with safety timeout
  useEffect(() => {
    loadAllData();
    const safetyTimer = setTimeout(() => {
      setLoading(false);
    }, 4000);
    return () => clearTimeout(safetyTimer);
  }, [loadAllData]);

  const loadBudgetLedger = useCallback(async () => {
    try {
      let url = `/admin/resellers/budget?period=${budgetPeriod}`;
      if (budgetPeriod === "custom" && budgetStartDate && budgetEndDate) {
        url += `&start_date=${budgetStartDate}&end_date=${budgetEndDate}`;
      }
      const res = await api.get(url);
      setResellerBudget(res.data);
      if (res.data.balances?.length > 0 && topUpSourceId === 0) {
        setTopUpSourceId(res.data.balances[0].id);
      }
    } catch (e) {
      console.error("Failed to load budget ledger", e);
    }
  }, [budgetPeriod, budgetStartDate, budgetEndDate, topUpSourceId]);

  useEffect(() => {
    if (activeTab === "budget") {
      loadBudgetLedger();
    }
  }, [activeTab, loadBudgetLedger]);

  const handleOpenUserPurchases = async (u: AdminUser) => {
    setUserPurchasesUser(u);
    setIsUserPurchasesOpen(true);
    setLoadingUserPurchases(true);
    try {
      const res = await api.get(`/admin/users/${u.telegram_id}/purchases`);
      setUserPurchasesList(res.data || []);
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to load user purchases", "error");
      setUserPurchasesList([]);
    } finally {
      setLoadingUserPurchases(false);
    }
  };

  const handleRecordTopUp = async (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseFloat(topUpAmount);
    if (isNaN(amt) || amt <= 0 || !topUpSourceId) {
      showToast("Please enter a valid deposit amount and select provider", "error");
      return;
    }
    try {
      await api.post(`/admin/resellers/${topUpSourceId}/topup`, {
        amount: amt,
        currency: "USD",
        payment_method: topUpMethod,
        note: topUpNote,
        tx_hash: topUpTxHash,
        update_balance: true
      });
      showToast(`Recorded $${amt.toFixed(2)} deposit into reseller wallet!`);
      setIsTopUpModalOpen(false);
      setTopUpAmount("");
      setTopUpNote("");
      setTopUpTxHash("");
      loadBudgetLedger();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to record topup", "error");
    }
  };

  const handleQrFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingQr(true);
    const reader = new FileReader();
    reader.onload = async () => {
      const base64Data = reader.result as string;
      try {
        await api.post("/admin/settings/upload-qr", { image_data: base64Data });
        setSettings(prev => ({ ...prev, nepal_qr_url: base64Data }));
        showToast("Nepal QR Code photo uploaded successfully!");
      } catch (err: any) {
        showToast(err.response?.data?.detail || "Failed to upload QR image", "error");
      } finally {
        setIsUploadingQr(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const sortedUsers = useMemo(() => {
    return [...users].sort((a, b) => {
      let valA: any = a[userSortField];
      let valB: any = b[userSortField];
      if (userSortField === "registration_date") {
        valA = new Date(a.registration_date || 0).getTime();
        valB = new Date(b.registration_date || 0).getTime();
      }
      if (valA < valB) return userSortOrder === "asc" ? -1 : 1;
      if (valA > valB) return userSortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [users, userSortField, userSortOrder]);

  const toggleUserSort = (field: "balance" | "purchases_count" | "total_spent" | "registration_date" | "telegram_id") => {
    if (userSortField === field) {
      setUserSortOrder(prev => prev === "asc" ? "desc" : "asc");
    } else {
      setUserSortField(field);
      setUserSortOrder("desc");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Product Handlers
  // ─────────────────────────────────────────────────────────────────────────

  const handleToggleProductActive = async (prod: AdminProduct) => {
    try {
      const res = await api.post(`/admin/products/${prod.id}/toggle-active`);
      setProducts(prev => prev.map(p => p.id === prod.id ? { ...p, is_active: res.data.is_active } : p));
      showToast(`${prod.name} is now ${res.data.is_active ? "ENABLED" : "DISABLED"}`);
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to toggle product status", "error");
    }
  };

  const handleToggleProductBadge = async (prod: AdminProduct, badgeType: "featured" | "hot" | "bestseller") => {
    try {
      const res = await api.post(`/admin/products/${prod.id}/toggle-badge?badge_type=${badgeType}`);
      setProducts(prev => prev.map(p => {
        if (p.id === prod.id) {
          return {
            ...p,
            is_featured: badgeType === "featured" ? res.data.value : p.is_featured,
            is_hot: badgeType === "hot" ? res.data.value : p.is_hot,
            is_bestseller: badgeType === "bestseller" ? res.data.value : p.is_bestseller,
          };
        }
        return p;
      }));
      showToast(`Updated ${badgeType} badge for ${prod.name}`);
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to update badge", "error");
    }
  };

  const handleSaveInlinePrice = async (prod: AdminProduct) => {
    const val = parseFloat(inlinePriceVal);
    if (isNaN(val) || val <= 0) {
      showToast("Invalid price amount", "error");
      return;
    }
    try {
      await api.patch(`/admin/products/${prod.id}`, { price: val });
      setProducts(prev => prev.map(p => p.id === prod.id ? { ...p, price: val } : p));
      setInlinePriceId(null);
      showToast(`Price for ${prod.name} updated to $${val.toFixed(2)}`);
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to update price", "error");
    }
  };

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProdName.trim() || !newProdPrice) {
      showToast("Please enter product name and price", "error");
      return;
    }
    try {
      await api.post("/admin/products", {
        name: newProdName.trim(),
        category_id: newProdCatId,
        price: parseFloat(newProdPrice),
        price_npr: newProdPriceNpr ? parseFloat(newProdPriceNpr) : null,
        cost_price: parseFloat(newProdCostPrice) || 0,
        warranty: newProdWarranty,
        note: newProdNote,
        description: newProdDesc,
        is_featured: newProdFeatured,
        is_hot: newProdHot,
        is_bestseller: newProdBestseller,
        badge_text: newProdBadgeText.trim() || null,
        auto_delivery: newProdAutoDelivery,
        delivery_template: newProdDeliveryTemplate.trim() || null,
        delivery_type: newProdDeliveryType || "instant",
        account_type: newProdAccountType || "preactivated",
        initial_keys: newProdInitialKeys.trim() || null,
      });
      showToast("Product created successfully!");
      setIsAddProductOpen(false);
      // Reset form
      setNewProdName("");
      setNewProdPrice("");
      setNewProdPriceNpr("");
      setNewProdCostPrice("");
      setNewProdDesc("");
      setNewProdAutoDelivery(true);
      setNewProdDeliveryType("instant");
      setNewProdAccountType("preactivated");
      setNewProdDeliveryTemplate("");
      setNewProdInitialKeys("");
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to create product", "error");
    }
  };

  const handleSaveEditProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProduct) return;
    try {
      await api.patch(`/admin/products/${editingProduct.id}`, {
        name: editingProduct.name,
        price: editingProduct.price,
        price_npr: editingProduct.price_npr,
        description: editingProduct.description,
        cost_price: editingProduct.cost_price,
        category_id: editingProduct.category_id,
        warranty: editingProduct.warranty,
        note: editingProduct.note,
        is_featured: editingProduct.is_featured,
        is_hot: editingProduct.is_hot,
        is_bestseller: editingProduct.is_bestseller,
        badge_text: editingProduct.badge_text,
        is_active: editingProduct.is_active,
        auto_delivery: editingProduct.auto_delivery !== false,
        delivery_template: editingProduct.delivery_template || null,
        delivery_type: editingProduct.delivery_type || "instant",
        account_type: editingProduct.account_type || "preactivated",
      });
      showToast(`Product ${editingProduct.name} updated!`);
      setIsEditProductOpen(false);
      setEditingProduct(null);
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to update product", "error");
    }
  };

  const handleAutoFulfillOrder = async (
    productId: string,
    productName: string,
    quantity: number,
    amountStr: string,
    customerEmail: string,
    orderId?: string
  ) => {
    try {
      showToast("⚡ Initiating multi-stage automated fulfillment pipeline...");
      const res = await api.post("/admin/orders/auto-fulfill", {
        product_id: productId,
        product_name: productName,
        quantity: quantity || 1,
        amount_str: amountStr,
        customer_email: customerEmail,
        order_id: orderId || "",
      });
      showToast(res.data.message || `Delivered to ${customerEmail}!`);
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Auto-fulfillment failed. Please check provider balance.", "error");
    }
  };

  const handleDeleteProduct = async (prod: AdminProduct) => {
    if (!confirm(`Are you sure you want to delete "${prod.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/products/${prod.id}`);
      setProducts(prev => prev.filter(p => p.id !== prod.id));
      showToast(`Product ${prod.name} deleted.`);
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to delete product", "error");
    }
  };

  const handleApplyBulkPrice = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(bulkChangeValue);
    if (isNaN(val)) {
      showToast("Please enter a valid change amount", "error");
      return;
    }
    try {
      const res = await api.post("/admin/products/bulk-price", {
        category_id: bulkCatId === "all" ? null : parseInt(bulkCatId),
        change_type: bulkChangeType,
        change_value: val,
        round_to_nearest: bulkRounding,
      });
      showToast(`Updated pricing on ${res.data.updated_products_count} products!`);
      setIsBulkPriceOpen(false);
      setBulkChangeValue("");
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to apply bulk pricing", "error");
    }
  };

  const handleOpenStockModal = async (prod: AdminProduct) => {
    setStockProduct(prod);
    setIsStockModalOpen(true);
    try {
      const res = await api.get(`/admin/products/${prod.id}/stock`);
      setStockItems(res.data.items || []);
    } catch (e) {
      setStockItems([]);
    }
  };

  const handleAddStockKeys = async () => {
    if (!stockProduct || !newStockKeys.trim()) return;
    try {
      const res = await api.post(`/admin/products/${stockProduct.id}/stock`, { keys: newStockKeys.trim() });
      showToast(`Added ${res.data.added_count} stock keys!`);
      setNewStockKeys("");
      const refreshed = await api.get(`/admin/products/${stockProduct.id}/stock`);
      setStockItems(refreshed.data.items || []);
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to add keys", "error");
    }
  };

  const handleDeleteStockItem = async (valId: number) => {
    if (!stockProduct) return;
    try {
      await api.delete(`/admin/products/${stockProduct.id}/stock/${valId}`);
      setStockItems(prev => prev.filter(i => i.id !== valId));
      showToast("Stock key deleted");
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to delete key", "error");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Category Handlers
  // ─────────────────────────────────────────────────────────────────────────

  const handleToggleCategoryActive = async (cat: AdminCategory) => {
    try {
      const res = await api.patch(`/admin/categories/${cat.id}`, { is_active: !cat.is_active });
      setCategories(prev => prev.map(c => c.id === cat.id ? { ...c, is_active: !c.is_active } : c));
      showToast(`Category ${cat.name} is now ${!cat.is_active ? "ACTIVE" : "DISABLED"}`);
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to toggle category", "error");
    }
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCatName.trim()) return;
    try {
      await api.post("/admin/categories", { name: newCatName.trim(), is_active: true });
      showToast("Category created!");
      setNewCatName("");
      setIsAddCategoryOpen(false);
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to create category", "error");
    }
  };

  const handleSaveEditCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCategory) return;
    try {
      await api.patch(`/admin/categories/${editingCategory.id}`, {
        name: editingCategory.name,
        is_active: editingCategory.is_active,
      });
      showToast("Category updated!");
      setIsEditCategoryOpen(false);
      setEditingCategory(null);
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to update category", "error");
    }
  };

  const handleDeleteCategory = async (cat: AdminCategory) => {
    if (!confirm(`Delete category "${cat.name}"? Products inside may become uncategorized.`)) return;
    try {
      await api.delete(`/admin/categories/${cat.id}`);
      setCategories(prev => prev.filter(c => c.id !== cat.id));
      showToast("Category deleted.");
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to delete category", "error");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Payments & Nepal QR Handlers
  // ─────────────────────────────────────────────────────────────────────────

  const handleApprovePayment = async (paymentId: number) => {
    try {
      const res = await api.post(`/admin/payments/${paymentId}/approve`);
      showToast(res.data.message || "Payment approved!");
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to approve payment", "error");
    }
  };

  const handleRejectPayment = async (paymentId: number) => {
    const reason = prompt("Enter rejection reason (optional):", "Invalid reference or payment not received");
    if (reason === null) return;
    try {
      const res = await api.post(`/admin/payments/${paymentId}/reject?reason=${encodeURIComponent(reason)}`);
      showToast(res.data.message || "Payment rejected.");
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to reject payment", "error");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // User Management Handlers
  // ─────────────────────────────────────────────────────────────────────────

  const handleAdjustBalance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!balanceUser) return;
    const amount = parseFloat(balanceAmount);
    if (isNaN(amount) || amount === 0) {
      showToast("Please enter a valid adjustment amount", "error");
      return;
    }
    try {
      const res = await api.post(`/admin/users/${balanceUser.telegram_id}/balance`, {
        amount,
        reason: balanceReason.trim()
      });
      showToast(`User balance adjusted! New balance: $${res.data.new_balance.toFixed(2)}`);
      setIsBalanceModalOpen(false);
      setBalanceAmount("");
      loadAllData();
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to adjust balance", "error");
    }
  };

  const handleToggleUserBlock = async (user: AdminUser) => {
    try {
      const res = await api.post(`/admin/users/${user.telegram_id}/toggle-block`);
      setUsers(prev => prev.map(u => u.telegram_id === user.telegram_id ? { ...u, is_blocked: res.data.is_blocked } : u));
      showToast(`User is now ${res.data.is_blocked ? "BLOCKED" : "UNBLOCKED"}`);
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to toggle block", "error");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Settings Handlers
  // ─────────────────────────────────────────────────────────────────────────

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await Promise.all([
        api.post("/admin/settings", settings),
        api.post("/admin/settings/delivery-templates", {
          template: settings.global_delivery_template || "",
          global_auto_delivery_enabled: settings.global_auto_delivery_enabled !== false,
        }),
      ]);
      showToast("Store rules and delivery templates saved successfully!");
    } catch (e: any) {
      showToast(e.response?.data?.detail || "Failed to save settings", "error");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Filtered Products Memo
  // ─────────────────────────────────────────────────────────────────────────

  const filteredProducts = useMemo(() => {
    return products.filter(p => {
      // Search
      if (prodSearch.trim()) {
        const s = prodSearch.toLowerCase().trim();
        const match = p.name.toLowerCase().includes(s) || 
                      p.id.toLowerCase().includes(s) || 
                      (p.note && p.note.toLowerCase().includes(s));
        if (!match) return false;
      }
      // Category
      if (prodCatFilter !== "all") {
        if (p.category_id !== parseInt(prodCatFilter)) return false;
      }
      // Status
      if (prodStatusFilter === "active" && !p.is_active) return false;
      if (prodStatusFilter === "disabled" && p.is_active) return false;

      // Stock
      if (prodStockFilter === "instock" && p.stock <= 0) return false;
      if (prodStockFilter === "lowstock" && (p.stock <= 0 || p.stock > 5)) return false;
      if (prodStockFilter === "outofstock" && p.stock > 0) return false;

      // Badge
      if (prodBadgeFilter === "featured" && !p.is_featured) return false;
      if (prodBadgeFilter === "hot" && !p.is_hot) return false;
      if (prodBadgeFilter === "bestseller" && !p.is_bestseller) return false;

      // Source
      if (prodSourceFilter === "local" && p.source_type !== "local") return false;
      if (prodSourceFilter === "reseller" && p.source_type !== "reseller") return false;

      return true;
    });
  }, [products, prodSearch, prodCatFilter, prodStatusFilter, prodStockFilter, prodBadgeFilter, prodSourceFilter]);

  if (needsAuth) {
    return (
      <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4 selection:bg-purple-500 selection:text-white relative overflow-hidden font-sans">
        <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[550px] h-[550px] rounded-full bg-purple-600/15 blur-[160px] pointer-events-none -translate-y-1/2" />
        <div className="fixed bottom-0 right-1/4 w-[400px] h-[400px] rounded-full bg-red-600/10 blur-[140px] pointer-events-none translate-y-1/3" />

        <div className="w-full max-w-md rounded-3xl p-8 bg-neutral-900/90 border border-purple-500/30 shadow-[0_0_50px_rgba(168,85,247,0.25)] relative z-10 backdrop-blur-xl">
          <div className="flex flex-col items-center text-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center text-2xl shadow-lg shadow-purple-500/30 mb-3 border border-purple-400/30">
              ⚡
            </div>
            <h1 className="text-2xl font-black tracking-tight text-white">
              KALI ADMIN MASTER
            </h1>
            <p className="text-xs text-neutral-400 font-medium mt-1">
              Protected Control Hub • Master Authentication
            </p>
          </div>

          {authError && (
            <div className="mb-5 p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2 font-medium">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{authError}</span>
            </div>
          )}

          <form onSubmit={handleAdminLogin} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-neutral-400 mb-1.5 block">Admin Username / Telegram ID</label>
              <div className="relative">
                <Users className="w-4 h-4 text-neutral-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  placeholder="prabin"
                  value={adminUsername}
                  onChange={e => setAdminUsername(e.target.value)}
                  className="w-full bg-neutral-950/80 border border-neutral-800 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium text-white focus:outline-none focus:border-purple-500 transition-all font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-neutral-400 mb-1.5 block">Master Admin Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-neutral-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={adminPassword}
                  onChange={e => setAdminPassword(e.target.value)}
                  className="w-full bg-neutral-950/80 border border-neutral-800 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium text-white focus:outline-none focus:border-purple-500 transition-all font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={authLoading}
              className="w-full py-3 mt-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-purple-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
            >
              {authLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <>Unlock Master Control Hub <ArrowUpRight className="w-4 h-4" /></>}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-neutral-800/80 flex items-center justify-between text-xs text-neutral-500">
            <Link href="/nepal" className="hover:text-purple-400 transition font-medium">
              ← Return to Live Store
            </Link>
            <span className="font-mono text-[10px]">Secure VPS Session</span>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center text-white">
        <RefreshCw className="w-10 h-10 animate-spin text-purple-500 mb-4" />
        <p className="text-neutral-400 font-medium tracking-wide">Loading Full-Control Admin Dashboard...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans selection:bg-purple-500 selection:text-white">
      {/* Toast Notification */}
      {toastMessage && (
        <div className={`fixed top-6 right-6 z-50 px-5 py-3.5 rounded-xl shadow-2xl flex items-center gap-3 backdrop-blur-md border animate-in slide-in-from-top duration-300 ${
          toastMessage.type === "success" 
            ? "bg-emerald-950/90 text-emerald-200 border-emerald-500/30" 
            : "bg-rose-950/90 text-rose-200 border-rose-500/30"
        }`}>
          {toastMessage.type === "success" ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertTriangle className="w-5 h-5 text-rose-400" />}
          <span className="font-medium text-sm">{toastMessage.text}</span>
        </div>
      )}

      {/* Top Admin Navigation Header */}
      <header className="sticky top-0 z-40 bg-neutral-900/80 backdrop-blur-xl border-b border-neutral-800 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/nepal" className="flex items-center gap-2 text-neutral-400 hover:text-white transition group text-sm font-medium">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span>Live Store</span>
          </Link>
          <div className="h-4 w-px bg-neutral-800" />
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center font-bold text-white shadow-lg shadow-purple-500/20">
              ⚡
            </div>
            <div>
              <h1 className="font-bold text-base tracking-tight bg-gradient-to-r from-white via-neutral-200 to-neutral-400 bg-clip-text text-transparent">
                KALI ADMIN MASTER
              </h1>
              <p className="text-[11px] text-neutral-500 font-mono flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live Control Hub • VPS Connected
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {pendingNepal.length > 0 && (
            <button
              onClick={() => setActiveTab("payments")}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-semibold hover:bg-amber-500/20 transition animate-pulse"
            >
              <QrCode className="w-3.5 h-3.5" />
              <span>{pendingNepal.length} Pending Nepal QR</span>
            </button>
          )}

          <button
            onClick={loadAllData}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-medium transition border border-neutral-700/60"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-purple-400" : ""}`} />
            <span>Sync</span>
          </button>
        </div>
      </header>

      {/* Main Layout Container */}
      <div className="flex-1 flex flex-col lg:flex-row">
        {/* Navigation Sidebar */}
        <aside className="w-full lg:w-64 bg-neutral-900/40 border-r border-neutral-800/80 p-4 flex flex-row lg:flex-col gap-1.5 overflow-x-auto">
          {[
            { id: "overview", label: "Overview", icon: LayoutDashboard, badge: null },
            { id: "products", label: "Products & Stock", icon: Package, badge: products.length },
            { id: "categories", label: "Categories", icon: Layers, badge: categories.length },
            { id: "payments", label: "Payments & QR", icon: CreditCard, badge: pendingNepal.length > 0 ? pendingNepal.length : null, badgeColor: "bg-amber-500 text-neutral-950 font-bold" },
            { id: "orders", label: "Orders Log", icon: ShoppingCart, badge: orders.length },
            { id: "users", label: "Customers", icon: Users, badge: users.length },
            { id: "budget", label: "Budget & Wallets", icon: Wallet, badge: resellerBudget ? `$${resellerBudget.total_balance_usd.toFixed(0)}` : null, badgeColor: "bg-emerald-950 text-emerald-300 border border-emerald-500/30 font-bold" },
            { id: "promocodes", label: "Promocodes", icon: Tag, badge: promocodes.length },
            { id: "settings", label: "Store & Geo Settings", icon: Bolt, badge: null },
          ].map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all shrink-0 ${
                  isActive
                    ? "bg-purple-600/15 text-purple-300 border border-purple-500/30 shadow-sm"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`w-4 h-4 ${isActive ? "text-purple-400" : "text-neutral-500"}`} />
                  <span>{tab.label}</span>
                </div>
                {tab.badge !== null && (
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${tab.badgeColor || "bg-neutral-800 text-neutral-400"}`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </aside>

        {/* Dynamic Tab Body */}
        <main className="flex-1 p-6 lg:p-8 max-w-7xl mx-auto w-full overflow-hidden">
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && stats && (
            <div className="space-y-8 animate-in fade-in duration-300">
              <div>
                <h2 className="text-xl font-bold text-white">Performance Overview</h2>
                <p className="text-xs text-neutral-400">Real-time store metrics, gross sales, and customer activity</p>
              </div>

              {/* KPI Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { label: "Total Gross Revenue", value: `$${stats.total_sales_usd.toFixed(2)}`, sub: `Today: $${stats.sales_today_usd.toFixed(2)}`, icon: DollarSign, color: "from-emerald-500/20 to-emerald-500/5", border: "border-emerald-500/30", text: "text-emerald-400" },
                  { label: "Net Est. Profit", value: `$${stats.total_profit_usd.toFixed(2)}`, sub: "Wholesale Margin Adjusted", icon: TrendingUp, color: "from-purple-500/20 to-purple-500/5", border: "border-purple-500/30", text: "text-purple-400" },
                  { label: "Total Orders Completed", value: stats.total_orders, sub: `Today: ${stats.orders_today} orders`, icon: ShoppingCart, color: "from-blue-500/20 to-blue-500/5", border: "border-blue-500/30", text: "text-blue-400" },
                  { label: "Registered Customers", value: stats.total_users, sub: `New today: +${stats.new_users_today}`, icon: Users, color: "from-indigo-500/20 to-indigo-500/5", border: "border-indigo-500/30", text: "text-indigo-400" },
                ].map((kpi, idx) => {
                  const Icon = kpi.icon;
                  return (
                    <div key={idx} className={`bg-gradient-to-b ${kpi.color} p-5 rounded-2xl border ${kpi.border} backdrop-blur-sm relative overflow-hidden`}>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-semibold text-neutral-400">{kpi.label}</span>
                        <div className={`p-2 rounded-xl bg-neutral-900/60 ${kpi.text}`}>
                          <Icon className="w-4 h-4" />
                        </div>
                      </div>
                      <div className="text-2xl font-bold text-white tracking-tight">{kpi.value}</div>
                      <p className="text-[11px] text-neutral-500 mt-1 font-mono">{kpi.sub}</p>
                    </div>
                  );
                })}
              </div>

              {/* Quick Actions Strip */}
              <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl p-6">
                <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <Bolt className="w-4 h-4 text-purple-400" />
                  <span>Master Shortcuts & Quick Operations</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                  <button
                    onClick={() => { setActiveTab("products"); setIsAddProductOpen(true); }}
                    className="flex items-center gap-3 p-3.5 rounded-xl bg-neutral-800/60 hover:bg-neutral-800 text-left border border-neutral-700/50 transition group"
                  >
                    <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400 group-hover:bg-purple-500 group-hover:text-white transition">
                      <Plus className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">Add New Product</div>
                      <div className="text-[10px] text-neutral-400">Add local item with keys</div>
                    </div>
                  </button>

                  <button
                    onClick={() => { setActiveTab("products"); setIsBulkPriceOpen(true); }}
                    className="flex items-center gap-3 p-3.5 rounded-xl bg-neutral-800/60 hover:bg-neutral-800 text-left border border-neutral-700/50 transition group"
                  >
                    <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500 group-hover:text-white transition">
                      <Percent className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">Bulk Price Adjust</div>
                      <div className="text-[10px] text-neutral-400">Modify category pricing %</div>
                    </div>
                  </button>

                  <button
                    onClick={() => setActiveTab("payments")}
                    className="flex items-center gap-3 p-3.5 rounded-xl bg-neutral-800/60 hover:bg-neutral-800 text-left border border-neutral-700/50 transition group"
                  >
                    <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400 group-hover:bg-amber-500 group-hover:text-white transition">
                      <QrCode className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">Verify Nepal QR</div>
                      <div className="text-[10px] text-neutral-400">{pendingNepal.length} pending review</div>
                    </div>
                  </button>

                  <button
                    onClick={() => setActiveTab("settings")}
                    className="flex items-center gap-3 p-3.5 rounded-xl bg-neutral-800/60 hover:bg-neutral-800 text-left border border-neutral-700/50 transition group"
                  >
                    <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-400 group-hover:bg-blue-500 group-hover:text-white transition">
                      <Globe className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">Store & Geo Rules</div>
                      <div className="text-[10px] text-neutral-400">NPR rate & IP filter</div>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: PRODUCTS & STOCK MANAGER */}
          {activeTab === "products" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              {/* Header Bar with Action Buttons */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2.5">
                    <span>Products & Catalog Master</span>
                    <span className="text-xs font-mono font-medium px-2.5 py-0.5 rounded-full bg-purple-950/80 border border-purple-500/30 text-purple-300">
                      {filteredProducts.length} Items
                    </span>
                  </h2>
                  <p className="text-xs text-neutral-400 mt-0.5">Control pricing, active visibility, badges, and digital keys stock</p>
                </div>

                <div className="flex items-center gap-2.5">
                  <button
                    onClick={() => setIsBulkPriceOpen(true)}
                    className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs font-semibold hover:bg-emerald-900/60 transition"
                  >
                    <Percent className="w-3.5 h-3.5" />
                    <span>Bulk Price Tool</span>
                  </button>
                  <button
                    onClick={() => setIsAddProductOpen(true)}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Product</span>
                  </button>
                </div>
              </div>

              {/* Comprehensive Multi-Filter Bar */}
              <div className="bg-neutral-900/70 border border-neutral-800 p-4 rounded-2xl space-y-3">
                <div className="flex flex-col md:flex-row items-center gap-3">
                  {/* Search */}
                  <div className="relative flex-1 w-full">
                    <Search className="w-4 h-4 text-neutral-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search items by name, ID, or keywords..."
                      value={prodSearch}
                      onChange={e => setProdSearch(e.target.value)}
                      className="w-full pl-9.5 pr-4 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-purple-500 transition"
                    />
                    {prodSearch && (
                      <button onClick={() => setProdSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-white">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  {/* Category Selector */}
                  <select
                    value={prodCatFilter}
                    onChange={e => setProdCatFilter(e.target.value)}
                    className="w-full md:w-48 py-2 px-3 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-neutral-200 focus:outline-none focus:border-purple-500 transition"
                  >
                    <option value="all">All Categories</option>
                    {categories.map(c => (
                      <option key={c.id} value={c.id.toString()}>{c.name}</option>
                    ))}
                    <option value="999">⚡ Wholesale Reseller APIs</option>
                  </select>

                  {/* Status Filter */}
                  <select
                    value={prodStatusFilter}
                    onChange={e => setProdStatusFilter(e.target.value as any)}
                    className="w-full md:w-36 py-2 px-3 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-neutral-200 focus:outline-none focus:border-purple-500 transition"
                  >
                    <option value="all">Status: All</option>
                    <option value="active">🟢 Active Only</option>
                    <option value="disabled">🔴 Disabled Only</option>
                  </select>
                </div>

                {/* Second Row: Stock, Badges, Source */}
                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-neutral-800/60">
                  <span className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider mr-1">Filter:</span>
                  
                  {/* Stock Pills */}
                  {[
                    { id: "all", label: "All Stock" },
                    { id: "instock", label: "In Stock" },
                    { id: "lowstock", label: "Low Stock (<5)" },
                    { id: "outofstock", label: "Out of Stock" }
                  ].map(pill => (
                    <button
                      key={pill.id}
                      onClick={() => setProdStockFilter(pill.id as any)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition ${
                        prodStockFilter === pill.id
                          ? "bg-purple-950/60 border-purple-500/50 text-purple-300 font-semibold"
                          : "bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-200"
                      }`}
                    >
                      {pill.label}
                    </button>
                  ))}

                  <div className="h-3 w-px bg-neutral-800 mx-1" />

                  {/* Badge Pills */}
                  {[
                    { id: "all", label: "All Badges" },
                    { id: "featured", label: "⭐ Featured" },
                    { id: "hot", label: "🔥 Hot" },
                    { id: "bestseller", label: "👑 Best Seller" },
                  ].map(pill => (
                    <button
                      key={pill.id}
                      onClick={() => setProdBadgeFilter(pill.id as any)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition ${
                        prodBadgeFilter === pill.id
                          ? "bg-indigo-950/60 border-indigo-500/50 text-indigo-300 font-semibold"
                          : "bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-200"
                      }`}
                    >
                      {pill.label}
                    </button>
                  ))}

                  <div className="h-3 w-px bg-neutral-800 mx-1" />

                  {/* Source Pills */}
                  {[
                    { id: "all", label: "All Sources" },
                    { id: "local", label: "📦 Local Inventory" },
                    { id: "reseller", label: "🌐 Reseller API" },
                  ].map(pill => (
                    <button
                      key={pill.id}
                      onClick={() => setProdSourceFilter(pill.id as any)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition ${
                        prodSourceFilter === pill.id
                          ? "bg-neutral-800 border-neutral-600 text-white font-semibold"
                          : "bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-200"
                      }`}
                    >
                      {pill.label}
                    </button>
                  ))}

                  {(prodSearch || prodCatFilter !== "all" || prodStatusFilter !== "all" || prodStockFilter !== "all" || prodBadgeFilter !== "all" || prodSourceFilter !== "all") && (
                    <button
                      onClick={() => {
                        setProdSearch("");
                        setProdCatFilter("all");
                        setProdStatusFilter("all");
                        setProdStockFilter("all");
                        setProdBadgeFilter("all");
                        setProdSourceFilter("all");
                      }}
                      className="text-[11px] text-purple-400 hover:underline ml-auto font-medium"
                    >
                      Clear Filters
                    </button>
                  )}
                </div>
              </div>

              {/* Products List Table / Cards */}
              <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 font-semibold uppercase tracking-wider text-[10px]">
                      <tr>
                        <th className="py-3 px-4">Item & Category</th>
                        <th className="py-3 px-4">Price (USD / NPR)</th>
                        <th className="py-3 px-4">Cost & Margin</th>
                        <th className="py-3 px-4">Stock</th>
                        <th className="py-3 px-4">Badges & Highlights</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/60">
                      {filteredProducts.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="text-center py-12 text-neutral-500">
                            No products match the selected criteria.
                          </td>
                        </tr>
                      ) : (
                        filteredProducts.map(prod => {
                          const nprPrice = Math.round(prod.price * (settings.npr_exchange_rate || 135));
                          const margin = prod.cost_price > 0 ? (((prod.price - prod.cost_price) / prod.price) * 100).toFixed(0) : "100";
                          const isEditingPrice = inlinePriceId === prod.id;

                          return (
                            <tr key={prod.id} className="hover:bg-neutral-800/30 transition group">
                              {/* Product Info */}
                              <td className="py-3.5 px-4">
                                <div className="font-semibold text-white group-hover:text-purple-300 transition text-sm">
                                  {prod.name}
                                </div>
                                <div className="flex items-center gap-2 mt-1">
                                  <span className="text-[10px] px-2 py-0.5 rounded-md bg-neutral-800 text-neutral-400 font-medium">
                                    {prod.category_name}
                                  </span>
                                  <span className={`text-[10px] px-2 py-0.5 rounded-md font-mono ${
                                    prod.source_type === "local" 
                                      ? "bg-purple-950/60 text-purple-300 border border-purple-500/30" 
                                      : "bg-blue-950/60 text-blue-300 border border-blue-500/30"
                                  }`}>
                                    {prod.source_name || prod.source_type}
                                  </span>
                                </div>
                              </td>

                              {/* Price Edit */}
                              <td className="py-3.5 px-4">
                                {isEditingPrice ? (
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-neutral-500">$</span>
                                    <input
                                      type="number"
                                      step="0.01"
                                      autoFocus
                                      value={inlinePriceVal}
                                      onChange={e => setInlinePriceVal(e.target.value)}
                                      onKeyDown={e => {
                                        if (e.key === "Enter") handleSaveInlinePrice(prod);
                                        if (e.key === "Escape") setInlinePriceId(null);
                                      }}
                                      className="w-20 px-2 py-1 bg-neutral-950 border border-purple-500 rounded text-xs text-white focus:outline-none"
                                    />
                                    <button
                                      onClick={() => handleSaveInlinePrice(prod)}
                                      className="p-1 rounded bg-purple-600 text-white hover:bg-purple-500"
                                    >
                                      <Check className="w-3.5 h-3.5" />
                                    </button>
                                    <button
                                      onClick={() => setInlinePriceId(null)}
                                      className="p-1 rounded bg-neutral-800 text-neutral-400 hover:text-white"
                                    >
                                      <X className="w-3.5 h-3.5" />
                                    </button>
                                  </div>
                                ) : (
                                  <div
                                    onClick={() => {
                                      setInlinePriceId(prod.id);
                                      setInlinePriceVal(prod.price.toString());
                                    }}
                                    className="cursor-pointer group/price flex items-baseline gap-2"
                                    title="Click to edit price"
                                  >
                                    <span className="font-bold text-white text-sm group-hover/price:text-purple-400 transition">
                                      ${prod.price.toFixed(2)}
                                    </span>
                                    <span className="text-[11px] text-neutral-500 font-mono">
                                      (Rs {nprPrice.toLocaleString()})
                                    </span>
                                    <Edit3 className="w-3 h-3 text-neutral-600 opacity-0 group-hover/price:opacity-100 transition" />
                                  </div>
                                )}
                              </td>

                              {/* Cost & Margin */}
                              <td className="py-3.5 px-4 font-mono">
                                <div className="text-neutral-400 text-xs">
                                  ${prod.cost_price.toFixed(2)}
                                </div>
                                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                                  parseInt(margin) >= 30 ? "text-emerald-400 bg-emerald-950/60" : "text-amber-400 bg-amber-950/60"
                                }`}>
                                  {margin}% Margin
                                </span>
                              </td>

                              {/* Stock */}
                              <td className="py-3.5 px-4">
                                <div className="flex items-center gap-2">
                                  <span className={`px-2.5 py-1 rounded-lg font-mono font-semibold text-xs ${
                                    prod.stock > 5 
                                      ? "bg-emerald-950/60 text-emerald-300 border border-emerald-500/30" 
                                      : prod.stock > 0 
                                      ? "bg-amber-950/60 text-amber-300 border border-amber-500/30"
                                      : "bg-rose-950/60 text-rose-300 border border-rose-500/30"
                                  }`}>
                                    {prod.stock} left
                                  </span>
                                  {prod.source_type === "local" && (
                                    <button
                                      onClick={() => handleOpenStockModal(prod)}
                                      className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-white transition"
                                      title="Manage Stock Keys"
                                    >
                                      <Key className="w-3.5 h-3.5" />
                                    </button>
                                  )}
                                </div>
                              </td>

                              {/* Badges Toggles */}
                              <td className="py-3.5 px-4">
                                <div className="flex items-center gap-1.5">
                                  <button
                                    onClick={() => handleToggleProductBadge(prod, "featured")}
                                    className={`p-1.5 rounded-lg border transition ${
                                      prod.is_featured 
                                        ? "bg-amber-500/20 border-amber-500/40 text-amber-300" 
                                        : "bg-neutral-900 border-neutral-800 text-neutral-600 hover:text-neutral-400"
                                    }`}
                                    title="Toggle Featured"
                                  >
                                    <Star className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleToggleProductBadge(prod, "hot")}
                                    className={`p-1.5 rounded-lg border transition ${
                                      prod.is_hot 
                                        ? "bg-rose-500/20 border-rose-500/40 text-rose-300" 
                                        : "bg-neutral-900 border-neutral-800 text-neutral-600 hover:text-neutral-400"
                                    }`}
                                    title="Toggle Hot"
                                  >
                                    <Flame className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleToggleProductBadge(prod, "bestseller")}
                                    className={`p-1.5 rounded-lg border transition ${
                                      prod.is_bestseller 
                                        ? "bg-purple-500/20 border-purple-500/40 text-purple-300" 
                                        : "bg-neutral-900 border-neutral-800 text-neutral-600 hover:text-neutral-400"
                                    }`}
                                    title="Toggle Best Seller"
                                  >
                                    <Award className="w-3.5 h-3.5" />
                                  </button>
                                  {prod.badge_text && (
                                    <span className="text-[10px] px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 font-semibold">
                                      {prod.badge_text}
                                    </span>
                                  )}
                                </div>
                              </td>

                              {/* Active Status Switch */}
                              <td className="py-3.5 px-4">
                                <button
                                  onClick={() => handleToggleProductActive(prod)}
                                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                                    prod.is_active ? "bg-emerald-600" : "bg-neutral-700"
                                  }`}
                                  title={prod.is_active ? "Click to Disable" : "Click to Enable"}
                                >
                                  <span
                                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                                      prod.is_active ? "translate-x-4.5" : "translate-x-1"
                                    }`}
                                  />
                                </button>
                              </td>

                              {/* Actions */}
                              <td className="py-3.5 px-4 text-right">
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    onClick={() => {
                                      setEditingProduct(prod);
                                      setIsEditProductOpen(true);
                                    }}
                                    className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white transition"
                                    title="Edit Product"
                                  >
                                    <Edit3 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteProduct(prod)}
                                    className="p-1.5 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-400 hover:text-rose-200 transition border border-rose-500/20"
                                    title="Delete Product"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: CATEGORIES */}
          {activeTab === "categories" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-white">Categories Management</h2>
                  <p className="text-xs text-neutral-400">Add, rename, enable/disable store categories</p>
                </div>
                <button
                  onClick={() => setIsAddCategoryOpen(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>New Category</span>
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {categories.map(cat => (
                  <div key={cat.id} className="bg-neutral-900/60 border border-neutral-800 p-5 rounded-2xl flex flex-col justify-between">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-bold text-white text-base">{cat.name}</h3>
                        <p className="text-xs text-neutral-500 mt-1 font-mono">{cat.products_count} Active Products</p>
                      </div>
                      <button
                        onClick={() => handleToggleCategoryActive(cat)}
                        className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border transition ${
                          cat.is_active 
                            ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300" 
                            : "bg-rose-950/60 border-rose-500/40 text-rose-300"
                        }`}
                      >
                        {cat.is_active ? "VISIBLE" : "HIDDEN"}
                      </button>
                    </div>

                    <div className="flex items-center justify-end gap-2 mt-6 pt-4 border-t border-neutral-800/80">
                      <button
                        onClick={() => {
                          setEditingCategory(cat);
                          setIsEditCategoryOpen(true);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs font-medium transition"
                      >
                        Rename
                      </button>
                      <button
                        onClick={() => handleDeleteCategory(cat)}
                        className="px-3 py-1.5 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-400 text-xs font-medium transition border border-rose-500/20"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: PAYMENTS & NEPAL QR APPROVALS */}
          {activeTab === "payments" && (
            <div className="space-y-8 animate-in fade-in duration-300">
              {/* Pending Nepal QR Section */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                      <QrCode className="w-5 h-5 text-amber-400" />
                      <span>Pending Nepal QR Payment Submissions</span>
                      <span className="text-xs font-mono font-medium px-2.5 py-0.5 rounded-full bg-amber-950/80 border border-amber-500/40 text-amber-300">
                        {pendingNepal.length} Pending
                      </span>
                    </h2>
                    <p className="text-xs text-neutral-400">Review eSewa / Fonepay customer receipts and 1-click verify</p>
                  </div>
                </div>

                {pendingNepal.length === 0 ? (
                  <div className="bg-neutral-900/40 border border-neutral-800/80 rounded-2xl p-8 text-center">
                    <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-60" />
                    <p className="text-sm text-neutral-400 font-medium">All Nepal QR payment submissions are verified and cleared!</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {pendingNepal.map(sub => (
                      <div key={sub.id} className="bg-neutral-900/70 border border-amber-500/30 p-5 rounded-2xl space-y-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <span className="text-xs font-mono font-bold text-amber-300">TX: {sub.tx_id}</span>
                            <p className="text-[11px] text-neutral-400 mt-0.5">
                              {sub.user_email || `User #${sub.user_id}`}
                            </p>
                          </div>
                          <div className="text-right">
                            <div className="text-base font-bold text-white">Rs {sub.amount_npr.toLocaleString()}</div>
                            <div className="text-[11px] text-neutral-400 font-mono">(${sub.amount_usd.toFixed(2)} USD)</div>
                          </div>
                        </div>

                        <div className="text-[11px] text-neutral-400 bg-neutral-950 p-2.5 rounded-xl border border-neutral-800 font-mono">
                          Submitted: {new Date(sub.created_at).toLocaleString()}
                        </div>

                        <div className="flex items-center gap-2 pt-2 border-t border-neutral-800">
                          <button
                            onClick={() => handleApprovePayment(sub.payment_id)}
                            className="flex-1 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition shadow-md shadow-emerald-600/20"
                          >
                            ✅ Approve & Credit
                          </button>
                          <button
                            onClick={() => handleRejectPayment(sub.payment_id)}
                            className="py-2 px-3 rounded-xl bg-rose-950/60 hover:bg-rose-900/60 text-rose-300 text-xs font-semibold border border-rose-500/30 transition"
                          >
                            ❌ Reject
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* General Payment Transactions Table */}
              <div>
                <h3 className="text-lg font-bold text-white mb-3">All Transaction Records</h3>
                <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 uppercase text-[10px]">
                      <tr>
                        <th className="py-3 px-4">Provider / Method</th>
                        <th className="py-3 px-4">Customer</th>
                        <th className="py-3 px-4">Amount</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/60">
                      {payments.map(p => (
                        <tr key={p.id} className="hover:bg-neutral-800/30 transition">
                          <td className="py-3 px-4 font-mono uppercase text-purple-300 font-medium">
                            {p.provider}
                          </td>
                          <td className="py-3 px-4 text-neutral-300">
                            {p.user_email || `User #${p.user_id}`}
                          </td>
                          <td className="py-3 px-4 font-bold text-white">
                            ${p.amount.toFixed(2)} {p.currency}
                          </td>
                          <td className="py-3 px-4">
                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${
                              p.status === "succeeded" 
                                ? "bg-emerald-950 text-emerald-300 border border-emerald-500/30" 
                                : p.status === "pending"
                                ? "bg-amber-950 text-amber-300 border border-amber-500/30"
                                : "bg-rose-950 text-rose-300 border border-rose-500/30"
                            }`}>
                              {p.status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-neutral-500 font-mono text-[11px]">
                            {new Date(p.created_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: ORDERS LOG */}
          {activeTab === "orders" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div>
                <h2 className="text-xl font-bold text-white">Delivered Orders & Fulfillment Log</h2>
                <p className="text-xs text-neutral-400">View customer purchases, item delivery credentials, and profit margins</p>
              </div>

              <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 uppercase text-[10px]">
                    <tr>
                      <th className="py-3 px-4">Order ID</th>
                      <th className="py-3 px-4">Product Name</th>
                      <th className="py-3 px-4">Customer</th>
                      <th className="py-3 px-4">Price / Profit</th>
                      <th className="py-3 px-4">Delivery Value</th>
                      <th className="py-3 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-800/60">
                    {orders.map(ord => (
                      <tr key={ord.id} className="hover:bg-neutral-800/30 transition">
                        <td className="py-3 px-4 font-mono text-neutral-400">#{ord.unique_id}</td>
                        <td className="py-3 px-4 font-semibold text-white">{ord.item_name}</td>
                        <td className="py-3 px-4 text-neutral-300">{ord.buyer_email || `User #${ord.buyer_id}`}</td>
                        <td className="py-3 px-4 font-mono">
                          <span className="font-bold text-emerald-400">${ord.price.toFixed(2)}</span>
                          <span className="text-[10px] text-neutral-500 ml-1">(+${ord.profit.toFixed(2)})</span>
                        </td>
                        <td className="py-3 px-4">
                          <button
                            onClick={() => {
                              setSelectedOrderCredentials(ord.value);
                              setIsOrderCredentialsOpen(true);
                            }}
                            className="flex items-center gap-1 px-2.5 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-[11px] font-mono"
                          >
                            <Eye className="w-3 h-3 text-purple-400" />
                            <span>View Keys</span>
                          </button>
                        </td>
                        <td className="py-3 px-4 text-neutral-500 font-mono text-[11px]">
                          {new Date(ord.bought_datetime).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 6: CUSTOMERS / USERS */}
          {activeTab === "users" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <Users className="w-5 h-5 text-purple-400" />
                    <span>Customer Accounts & Wallets</span>
                    <span className="text-xs font-mono font-medium px-2.5 py-0.5 rounded-full bg-purple-950/80 border border-purple-500/40 text-purple-300">
                      {users.length} Total
                    </span>
                  </h2>
                  <p className="text-xs text-neutral-400">Click column headers to sort by balance, purchases, total spend, or registration date</p>
                </div>
              </div>

              <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl overflow-hidden shadow-xl">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 uppercase text-[10px]">
                      <tr>
                        <th 
                          onClick={() => toggleUserSort("telegram_id")}
                          className="py-3.5 px-4 cursor-pointer hover:text-white transition select-none"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>User ID / Email</span>
                            {userSortField === "telegram_id" ? (userSortOrder === "asc" ? <ArrowUp className="w-3 h-3 text-purple-400" /> : <ArrowDown className="w-3 h-3 text-purple-400" />) : <ArrowUpDown className="w-3 h-3 text-neutral-600" />}
                          </div>
                        </th>
                        <th className="py-3.5 px-4">Role</th>
                        <th 
                          onClick={() => toggleUserSort("balance")}
                          className="py-3.5 px-4 cursor-pointer hover:text-white transition select-none"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>Wallet Balance</span>
                            {userSortField === "balance" ? (userSortOrder === "asc" ? <ArrowUp className="w-3 h-3 text-purple-400" /> : <ArrowDown className="w-3 h-3 text-purple-400" />) : <ArrowUpDown className="w-3 h-3 text-neutral-600" />}
                          </div>
                        </th>
                        <th 
                          onClick={() => toggleUserSort("total_spent")}
                          className="py-3.5 px-4 cursor-pointer hover:text-white transition select-none"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>Purchases / Total Spent</span>
                            {userSortField === "total_spent" || userSortField === "purchases_count" ? (userSortOrder === "asc" ? <ArrowUp className="w-3 h-3 text-purple-400" /> : <ArrowDown className="w-3 h-3 text-purple-400" />) : <ArrowUpDown className="w-3 h-3 text-neutral-600" />}
                          </div>
                        </th>
                        <th 
                          onClick={() => toggleUserSort("registration_date")}
                          className="py-3.5 px-4 cursor-pointer hover:text-white transition select-none"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>Registered</span>
                            {userSortField === "registration_date" ? (userSortOrder === "asc" ? <ArrowUp className="w-3 h-3 text-purple-400" /> : <ArrowDown className="w-3 h-3 text-purple-400" />) : <ArrowUpDown className="w-3 h-3 text-neutral-600" />}
                          </div>
                        </th>
                        <th className="py-3.5 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/60 font-sans">
                      {sortedUsers.map(u => (
                        <tr key={u.telegram_id} className="hover:bg-neutral-800/30 transition">
                          <td className="py-3.5 px-4">
                            <div className="font-semibold text-white">{u.email || `User #${u.telegram_id}`}</div>
                            <div className="text-[10px] text-neutral-500 font-mono">TG ID: {u.telegram_id}</div>
                          </td>
                          <td className="py-3.5 px-4">
                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                              u.role_name === "ADMIN" ? "bg-purple-950 text-purple-300 border border-purple-500/30" : "bg-neutral-800 text-neutral-400"
                            }`}>
                              {u.role_name}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 font-mono font-bold text-emerald-400 text-sm">
                            ${u.balance.toFixed(2)}
                          </td>
                          <td className="py-3.5 px-4 font-mono">
                            <span className="text-white font-semibold">{u.purchases_count} items</span>
                            <span className="text-neutral-400 ml-1.5 font-bold">(${u.total_spent.toFixed(2)})</span>
                          </td>
                          <td className="py-3.5 px-4 text-neutral-400 font-mono text-[11px]">
                            {u.registration_date ? new Date(u.registration_date).toLocaleDateString() : "N/A"}
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleOpenUserPurchases(u)}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-950/60 hover:bg-purple-900/60 text-purple-300 text-xs font-medium border border-purple-500/30 transition shadow-sm"
                                title="View item deliveries & full purchase ledger"
                              >
                                <Package className="w-3.5 h-3.5" />
                                <span>Purchases ({u.purchases_count})</span>
                              </button>
                              <button
                                onClick={() => {
                                  setBalanceUser(u);
                                  setIsBalanceModalOpen(true);
                                }}
                                className="px-2.5 py-1 rounded-lg bg-emerald-950/60 hover:bg-emerald-900/60 text-emerald-300 text-xs font-medium border border-emerald-500/30 transition"
                              >
                                Adjust $
                              </button>
                              <button
                                onClick={() => handleToggleUserBlock(u)}
                                className={`p-1.5 rounded-lg border transition ${
                                  u.is_blocked 
                                    ? "bg-rose-950/60 border-rose-500/40 text-rose-300" 
                                    : "bg-neutral-800 border-neutral-700 text-neutral-400 hover:text-white"
                                }`}
                                title={u.is_blocked ? "Unblock User" : "Block User"}
                              >
                                {u.is_blocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: RESELLER API BUDGET & WALLET TRACKING */}
          {activeTab === "budget" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <Wallet className="w-5 h-5 text-emerald-400" />
                    <span>Reseller API Balances & Wholesale Budget Ledger</span>
                  </h2>
                  <p className="text-xs text-neutral-400">Track external supplier balances, loaded funds, order fulfillment spend, and net margins</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIsTopUpModalOpen(true)}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/20 transition cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Record API Top-up</span>
                  </button>
                </div>
              </div>

              {/* Time Period Filter Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-3 bg-neutral-900/60 p-3 rounded-2xl border border-neutral-800">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-neutral-400 font-medium mr-1 flex items-center gap-1">
                    <Filter className="w-3.5 h-3.5" /> Filter Range:
                  </span>
                  {[
                    { id: "all", label: "All Time" },
                    { id: "day", label: "Today (24h)" },
                    { id: "week", label: "Last 7 Days" },
                    { id: "month", label: "Last 30 Days" },
                    { id: "custom", label: "Custom Range" },
                  ].map(p => (
                    <button
                      key={p.id}
                      onClick={() => setBudgetPeriod(p.id as any)}
                      className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                        budgetPeriod === p.id 
                          ? "bg-purple-600 text-white shadow" 
                          : "bg-neutral-800/80 text-neutral-300 hover:bg-neutral-700"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                {budgetPeriod === "custom" && (
                  <div className="flex items-center gap-2">
                    <input
                      type="date"
                      value={budgetStartDate}
                      onChange={e => setBudgetStartDate(e.target.value)}
                      className="px-2.5 py-1 bg-neutral-950 border border-neutral-700 rounded-lg text-xs text-white"
                    />
                    <span className="text-neutral-500 text-xs">to</span>
                    <input
                      type="date"
                      value={budgetEndDate}
                      onChange={e => setBudgetEndDate(e.target.value)}
                      className="px-2.5 py-1 bg-neutral-950 border border-neutral-700 rounded-lg text-xs text-white"
                    />
                    <button
                      onClick={loadBudgetLedger}
                      className="px-3 py-1 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg"
                    >
                      Apply
                    </button>
                  </div>
                )}
              </div>

              {/* KPI Summary Cards */}
              {resellerBudget && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-gradient-to-b from-emerald-500/20 to-emerald-500/5 p-5 rounded-2xl border border-emerald-500/30 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-neutral-400">Total API Wallet Balances</span>
                      <Wallet className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div className="text-2xl font-bold font-mono text-emerald-400">
                      ${resellerBudget.total_balance_usd.toFixed(2)}
                    </div>
                    <div className="text-[11px] text-neutral-400 mt-1">Available across active providers</div>
                  </div>

                  <div className="bg-gradient-to-b from-rose-500/20 to-rose-500/5 p-5 rounded-2xl border border-rose-500/30 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-neutral-400">Period Wholesale Spend</span>
                      <TrendingDown className="w-4 h-4 text-rose-400" />
                    </div>
                    <div className="text-2xl font-bold font-mono text-rose-400">
                      ${resellerBudget.total_spent_usd.toFixed(2)}
                    </div>
                    <div className="text-[11px] text-neutral-400 mt-1">{resellerBudget.orders_count} wholesale orders placed</div>
                  </div>

                  <div className="bg-gradient-to-b from-purple-500/20 to-purple-500/5 p-5 rounded-2xl border border-purple-500/30 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-neutral-400">Period Top-ups Loaded</span>
                      <TrendingUp className="w-4 h-4 text-purple-400" />
                    </div>
                    <div className="text-2xl font-bold font-mono text-purple-400">
                      ${resellerBudget.total_loaded_usd.toFixed(2)}
                    </div>
                    <div className="text-[11px] text-neutral-400 mt-1">Deposits in selected range</div>
                  </div>

                  <div className="bg-gradient-to-b from-blue-500/20 to-blue-500/5 p-5 rounded-2xl border border-blue-500/30 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-neutral-400">Active API Providers</span>
                      <Layers className="w-4 h-4 text-blue-400" />
                    </div>
                    <div className="text-2xl font-bold font-mono text-blue-400">
                      {resellerBudget.balances.length} Sources
                    </div>
                    <div className="text-[11px] text-neutral-400 mt-1">Canboso, GGSoma, CGPT, etc.</div>
                  </div>
                </div>
              )}

              {/* Provider Wallets Live Grid */}
              <div className="space-y-3">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-purple-400" />
                  <span>Wholesale Provider Balances</span>
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {resellerBudget?.balances.map(source => (
                    <div key={source.id} className="bg-neutral-900/70 border border-neutral-800 p-5 rounded-2xl flex flex-col justify-between space-y-3 hover:border-neutral-700 transition">
                      <div className="flex items-start justify-between">
                        <div>
                          <span className="text-xs font-mono font-bold text-purple-300 uppercase tracking-wider">{source.name}</span>
                          <p className="text-[11px] text-neutral-400 mt-0.5">Provider ID: #{source.id}</p>
                        </div>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                          source.balance < 5 
                            ? "bg-rose-950 text-rose-300 border border-rose-500/30 animate-pulse" 
                            : "bg-emerald-950 text-emerald-300 border border-emerald-500/30"
                        }`}>
                          {source.balance < 5 ? "LOW BALANCE" : "HEALTHY"}
                        </span>
                      </div>

                      <div>
                        <div className="text-2xl font-bold font-mono text-white">
                          ${source.balance.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-neutral-500 font-mono mt-0.5">
                          {source.last_synced ? `Synced: ${new Date(source.last_synced).toLocaleTimeString()}` : "Live API ready"}
                        </div>
                      </div>

                      <button
                        onClick={() => {
                          setTopUpSourceId(source.id);
                          setIsTopUpModalOpen(true);
                        }}
                        className="w-full py-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-semibold rounded-xl transition border border-neutral-700/60 flex items-center justify-center gap-1.5"
                      >
                        <Plus className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Record Deposit</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Top-up History Ledger */}
              <div className="space-y-3">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Clock className="w-4 h-4 text-purple-400" />
                  <span>Wholesale Top-Up & Deposit History</span>
                </h3>

                <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-2xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 uppercase text-[10px]">
                      <tr>
                        <th className="py-3 px-4">Provider</th>
                        <th className="py-3 px-4">Amount</th>
                        <th className="py-3 px-4">Payment Method</th>
                        <th className="py-3 px-4">Note / Reason</th>
                        <th className="py-3 px-4">Tx Hash / Ref</th>
                        <th className="py-3 px-4">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/60 font-sans">
                      {resellerBudget?.topups.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-neutral-500 text-xs">
                            No top-ups recorded in this date range. Click "+ Record API Top-up" to log deposits.
                          </td>
                        </tr>
                      ) : (
                        resellerBudget?.topups.map(t => (
                          <tr key={t.id} className="hover:bg-neutral-800/30 transition">
                            <td className="py-3 px-4 font-bold text-purple-300 font-mono uppercase">{t.source_name}</td>
                            <td className="py-3 px-4 font-mono font-bold text-emerald-400 text-sm">
                              +${t.amount.toFixed(2)}
                            </td>
                            <td className="py-3 px-4 text-neutral-300 font-mono text-[11px]">{t.payment_method || "USDT"}</td>
                            <td className="py-3 px-4 text-neutral-300">{t.note || "-"}</td>
                            <td className="py-3 px-4 text-neutral-500 font-mono text-[11px] truncate max-w-[120px]">{t.tx_hash || "-"}</td>
                            <td className="py-3 px-4 text-neutral-400 font-mono text-[11px]">
                              {t.created_at ? new Date(t.created_at).toLocaleString() : ""}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 8: PROMOCODES */}
          {activeTab === "promocodes" && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-white">Discount Promocodes</h2>
                  <p className="text-xs text-neutral-400">Create discount codes for customer promotions</p>
                </div>
                <button
                  onClick={() => setIsAddPromoOpen(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Promocode</span>
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {promocodes.map(promo => (
                  <div key={promo.id} className="bg-neutral-900/60 border border-neutral-800 p-5 rounded-2xl flex flex-col justify-between">
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="text-base font-bold text-purple-300 font-mono tracking-wider">{promo.code}</span>
                        <p className="text-xs text-neutral-400 mt-1">
                          {promo.discount_type === "percent" ? `${promo.discount_value}% Discount` : `$${promo.discount_value} Flat Off`}
                        </p>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-neutral-800 text-neutral-400">
                        {promo.current_uses} / {promo.max_uses === 0 ? "∞" : promo.max_uses} used
                      </span>
                    </div>

                    <div className="flex items-center justify-end mt-4 pt-3 border-t border-neutral-800">
                      <button
                        onClick={async () => {
                          if (!confirm(`Delete promocode ${promo.code}?`)) return;
                          await api.delete(`/admin/promocodes/${promo.id}`);
                          setPromocodes(prev => prev.filter(p => p.id !== promo.id));
                          showToast("Promocode deleted");
                        }}
                        className="text-xs text-rose-400 hover:underline"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 9: STORE SETTINGS, QR UPLOADER & WEBSITE COPY */}
          {activeTab === "settings" && (
            <div className="space-y-8 max-w-4xl animate-in fade-in duration-300">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Bolt className="w-5 h-5 text-purple-400" />
                  <span>Store Rules, Nepal QR & Website Customizer</span>
                </h2>
                <p className="text-xs text-neutral-400">Manage Geo-IP restrictions, upload QR photos, and edit customer-facing announcement banners & mantra</p>
              </div>

              <form onSubmit={handleSaveSettings} className="space-y-8">
                {/* Section 1: Customer Site Top Copy & Sacred Mantra */}
                <div className="bg-neutral-900/60 border border-purple-500/30 p-6 rounded-3xl space-y-5 shadow-lg">
                  <div className="border-b border-neutral-800 pb-3 flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-white flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-purple-400" />
                        <span>Customer Website Header & Announcement Copy</span>
                      </h3>
                      <p className="text-xs text-neutral-400">Edit the top sacred mantra bar, hero title, and broadcast announcements</p>
                    </div>
                  </div>

                  {/* Mantra Bar Text */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-neutral-300 flex items-center justify-between">
                      <span>Top Sacred Mantra Bar Text</span>
                      <span className="text-neutral-500 text-[11px]">Freezes at the very top of both stores</span>
                    </label>
                    <input
                      type="text"
                      value={settings.mantra_bar_text}
                      onChange={e => setSettings(prev => ({ ...prev, mantra_bar_text: e.target.value }))}
                      placeholder="॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥"
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-purple-200 focus:outline-none focus:border-purple-500 font-sans"
                    />
                  </div>

                  {/* Hero Title and Subtitle */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-neutral-300">Hero Section Main Title</label>
                      <input
                        type="text"
                        value={settings.hero_title}
                        onChange={e => setSettings(prev => ({ ...prev, hero_title: e.target.value }))}
                        className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white focus:outline-none focus:border-purple-500"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-neutral-300">Hero Subtitle / Description</label>
                      <input
                        type="text"
                        value={settings.hero_subtitle}
                        onChange={e => setSettings(prev => ({ ...prev, hero_subtitle: e.target.value }))}
                        className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white focus:outline-none focus:border-purple-500"
                      />
                    </div>
                  </div>

                  {/* Announcement Banner Box */}
                  <div className="p-4 bg-neutral-950/80 border border-neutral-800 rounded-2xl space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs font-semibold text-white">Broadcast Announcement Banner</span>
                        <p className="text-[11px] text-neutral-400">Display an emergency alert or promotional banner to visitors</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSettings(prev => ({ ...prev, announcement_banner_enabled: !prev.announcement_banner_enabled }))}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          settings.announcement_banner_enabled ? "bg-purple-600" : "bg-neutral-700"
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            settings.announcement_banner_enabled ? "translate-x-6" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>

                    {settings.announcement_banner_enabled && (
                      <div className="space-y-3 pt-3 border-t border-neutral-800">
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-neutral-300">Announcement Banner Text</label>
                          <input
                            type="text"
                            value={settings.announcement_banner_text}
                            onChange={e => setSettings(prev => ({ ...prev, announcement_banner_text: e.target.value }))}
                            placeholder="e.g. ⚡ Special Dashain Offer: 20% Extra Wallet Bonus on all Nepal QR Deposits!"
                            className="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-xl text-xs text-amber-200 focus:outline-none focus:border-purple-500"
                          />
                        </div>

                        <div className="flex items-center gap-3">
                          <label className="text-xs text-neutral-400">Banner Theme:</label>
                          {["info", "warning", "success"].map(type => (
                            <label key={type} className="flex items-center gap-1.5 cursor-pointer text-xs uppercase text-neutral-300 font-mono">
                              <input
                                type="radio"
                                name="bannerType"
                                value={type}
                                checked={settings.announcement_banner_type === type}
                                onChange={e => setSettings(prev => ({ ...prev, announcement_banner_type: e.target.value }))}
                              />
                              <span>{type}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Section 2: Nepal QR Code Uploader & Payment Messaging */}
                <div className="bg-neutral-900/60 border border-amber-500/30 p-6 rounded-3xl space-y-5 shadow-lg">
                  <div className="border-b border-neutral-800 pb-3">
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <QrCode className="w-5 h-5 text-amber-400" />
                      <span>Nepal QR Merchant & Payment Photo Uploader</span>
                    </h3>
                    <p className="text-xs text-neutral-400">Upload your direct eSewa / Khalti / Fonepay QR image and customize the checkout instructions</p>
                  </div>

                  {/* QR Image Preview & Upload Controls */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-start">
                    <div className="flex flex-col items-center justify-center p-4 bg-neutral-950 border border-neutral-800 rounded-2xl text-center space-y-3">
                      <div className="text-xs font-semibold text-neutral-300">Current QR Code Image</div>
                      {settings.nepal_qr_url ? (
                        <div className="relative group">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={settings.nepal_qr_url}
                            alt="Nepal QR Code"
                            className="w-36 h-36 object-contain rounded-xl border border-amber-500/40 bg-white p-1"
                          />
                          <span className="text-[10px] text-emerald-400 block mt-1.5 font-mono">✓ Active in Store</span>
                        </div>
                      ) : (
                        <div className="w-36 h-36 rounded-xl border-2 border-dashed border-neutral-700 flex flex-col items-center justify-center text-neutral-500 p-2">
                          <QrCode className="w-8 h-8 mb-1" />
                          <span className="text-[10px]">No image uploaded</span>
                        </div>
                      )}

                      <label className="w-full py-2 px-3 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl cursor-pointer transition shadow-md flex items-center justify-center gap-1.5">
                        <Upload className="w-3.5 h-3.5" />
                        <span>{isUploadingQr ? "Uploading..." : "Upload New QR Photo"}</span>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleQrFileUpload}
                          disabled={isUploadingQr}
                          className="hidden"
                        />
                      </label>
                    </div>

                    <div className="md:col-span-2 space-y-3">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-neutral-300">Gateway Title</label>
                          <input
                            type="text"
                            value={settings.nepal_qr_title}
                            onChange={e => setSettings(prev => ({ ...prev, nepal_qr_title: e.target.value }))}
                            placeholder="eSewa / Khalti / Fonepay Direct QR"
                            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white focus:outline-none focus:border-purple-500"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-neutral-300">Account Holder Name</label>
                          <input
                            type="text"
                            value={settings.nepal_qr_account_name}
                            onChange={e => setSettings(prev => ({ ...prev, nepal_qr_account_name: e.target.value }))}
                            placeholder="Kali Store Nepal"
                            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white focus:outline-none focus:border-purple-500"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-neutral-300">eSewa / Fonepay Phone / ID</label>
                          <input
                            type="text"
                            value={settings.nepal_qr_account_id}
                            onChange={e => setSettings(prev => ({ ...prev, nepal_qr_account_id: e.target.value }))}
                            placeholder="98XXXXXXXX"
                            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white font-mono focus:outline-none focus:border-purple-500"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-neutral-300">NPR per $1 USD Exchange Multiplier</label>
                          <input
                            type="number"
                            step="0.5"
                            value={settings.npr_exchange_rate}
                            onChange={e => setSettings(prev => ({ ...prev, npr_exchange_rate: parseFloat(e.target.value) || 135 }))}
                            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-emerald-400 font-mono font-bold focus:outline-none focus:border-purple-500"
                          />
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-neutral-300">Customer Payment Page Instructions</label>
                        <textarea
                          rows={2}
                          value={settings.nepal_qr_instructions}
                          onChange={e => setSettings(prev => ({ ...prev, nepal_qr_instructions: e.target.value }))}
                          placeholder="Scan QR with eSewa/Khalti/Fonepay, transfer exact NPR amount, then submit your Tx Reference ID below."
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white focus:outline-none focus:border-purple-500 leading-relaxed"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section 3: Geo-IP Rules */}
                <div className="bg-neutral-900/60 border border-neutral-800 p-6 rounded-3xl space-y-4 shadow-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-white flex items-center gap-2">
                        <Globe className="w-4 h-4 text-purple-400" />
                        <span>Automatic Nepal IP-Based Store Restriction</span>
                      </div>
                      <p className="text-xs text-neutral-400 mt-0.5">
                        When enabled, visitors detected from Nepal are automatically locked into Nepal Store (NPR) and restricted from global crypto stores.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSettings(prev => ({ ...prev, geo_filtering_enabled: !prev.geo_filtering_enabled }))}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        settings.geo_filtering_enabled ? "bg-purple-600" : "bg-neutral-700"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          settings.geo_filtering_enabled ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                </div>

                {/* Section 4: Auto Delivery Engine & Message Template Customizer */}
                <div className="bg-neutral-900/60 border border-emerald-500/30 p-6 rounded-3xl space-y-5 shadow-lg">
                  <div className="border-b border-neutral-800 pb-3 flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-white flex items-center gap-2">
                        <Bolt className="w-5 h-5 text-emerald-400" />
                        <span>Automated API Purchase & Email Delivery Engine</span>
                      </h3>
                      <p className="text-xs text-neutral-400">
                        Automatically order from wholesale APIs and dispatch credentials directly to customer email with multi-stage Telegram alerts
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSettings(prev => ({ ...prev, global_auto_delivery_enabled: !(prev.global_auto_delivery_enabled !== false) }))}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        settings.global_auto_delivery_enabled !== false ? "bg-emerald-600" : "bg-neutral-700"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          settings.global_auto_delivery_enabled !== false ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>

                  <div className="p-3.5 bg-neutral-950 border border-neutral-800 rounded-2xl space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-neutral-300">Global Auto-Delivery Status:</span>
                      <span className={`font-mono font-bold px-2.5 py-0.5 rounded-full text-[11px] ${
                        settings.global_auto_delivery_enabled !== false ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40" : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                      }`}>
                        {settings.global_auto_delivery_enabled !== false ? "⚡ ACTIVE (API + Vault Auto Dispatch)" : "⏸️ DISABLED (Manual Verification Queue)"}
                      </span>
                    </div>
                    <div className="text-[11px] text-neutral-400 leading-relaxed">
                      Real-time stage tracking updates (<code>[STAGE 1/4]</code> ➔ <code>[STAGE 2/4]</code> ➔ <code>[STAGE 3/4]</code> ➔ <code>[STAGE 4/4]</code>) are automatically broadcasted to the support/alert Telegram channel for complete administrative transparency.
                    </div>
                  </div>

                  {/* Delivery Message Template Editor */}
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-neutral-300 flex items-center justify-between">
                      <span>Default Delivery Message Template (Emails & Bot)</span>
                      <span className="text-neutral-500 text-[11px]">Used whenever a product does not have an item override</span>
                    </label>
                    <textarea
                      rows={5}
                      value={settings.global_delivery_template || ""}
                      onChange={e => setSettings(prev => ({ ...prev, global_delivery_template: e.target.value }))}
                      placeholder="Hello {customer_email},&#10;&#10;Your order for {product_name} (x{quantity}) is ready!&#10;&#10;Credentials:&#10;{credentials}&#10;&#10;Warranty: {warranty}&#10;Support: {support_contact}"
                      className="w-full px-3.5 py-2.5 bg-neutral-950 border border-neutral-800 rounded-xl text-xs text-white font-mono leading-relaxed focus:outline-none focus:border-emerald-500"
                    />

                    {/* Placeholder helper chips */}
                    <div className="pt-1">
                      <span className="text-[11px] text-neutral-400 font-semibold block mb-1.5">Available dynamic placeholders (click to insert):</span>
                      <div className="flex flex-wrap gap-1.5">
                        {[
                          "{customer_email}",
                          "{product_name}",
                          "{quantity}",
                          "{credentials}",
                          "{amount}",
                          "{warranty}",
                          "{note}",
                          "{tx_id}",
                          "{support_contact}"
                        ].map(tag => (
                          <button
                            key={tag}
                            type="button"
                            onClick={() => setSettings(prev => ({ ...prev, global_delivery_template: (prev.global_delivery_template || "") + " " + tag }))}
                            className="px-2 py-0.5 bg-neutral-800 hover:bg-neutral-700 text-purple-300 font-mono text-[10px] rounded-lg border border-neutral-700 transition"
                          >
                            + {tag}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="submit"
                    className="px-8 py-3 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold shadow-xl shadow-purple-600/30 transition cursor-pointer"
                  >
                    Save All Store Settings
                  </button>
                </div>
              </form>
            </div>
          )}
        </main>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: ADD PRODUCT */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isAddProductOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-xl rounded-3xl p-6 space-y-5 my-8">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-purple-400" />
                <span>Create New Product</span>
              </h3>
              <button onClick={() => setIsAddProductOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateProduct} className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-semibold text-neutral-300">Product Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Netflix 1 Month Ultra HD Account"
                  value={newProdName}
                  onChange={e => setNewProdName(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-neutral-300">Product Description</label>
                <textarea
                  rows={3}
                  value={newProdDesc}
                  onChange={e => setNewProdDesc(e.target.value)}
                  placeholder="Enter detailed description, key features, instructions..."
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500 leading-relaxed"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Category *</label>
                  <select
                    value={newProdCatId}
                    onChange={e => setNewProdCatId(parseInt(e.target.value))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  >
                    {categories.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Selling Price ($ USD) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="4.99"
                    value={newProdPrice}
                    onChange={e => setNewProdPrice(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500 font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Price (NPR रु) <span className="text-neutral-500 font-normal">Override</span></label>
                  <input
                    type="number"
                    step="1"
                    placeholder={`Auto (Rs. ${newProdPrice ? Math.round(parseFloat(newProdPrice) * (settings.npr_exchange_rate || 135)) : 0})`}
                    value={newProdPriceNpr}
                    onChange={e => setNewProdPriceNpr(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Cost Price ($ USD)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="2.50"
                    value={newProdCostPrice}
                    onChange={e => setNewProdCostPrice(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500 font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Warranty</label>
                  <input
                    type="text"
                    value={newProdWarranty}
                    onChange={e => setNewProdWarranty(e.target.value)}
                    placeholder="e.g. 24 Hours, 30 Days"
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Badge Text (Optional)</label>
                  <input
                    type="text"
                    value={newProdBadgeText}
                    onChange={e => setNewProdBadgeText(e.target.value)}
                    placeholder="e.g. 50% OFF, LIMITED"
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              {/* Delivery Mode & Account Type Selectors */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Delivery Mode</label>
                  <select
                    value={newProdDeliveryType}
                    onChange={e => setNewProdDeliveryType(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="instant">⚡ Instant Delivery (Automated)</option>
                    <option value="manual">⏱️ Manual Dispatch (Staff / Pre-order)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Account / Key Type</label>
                  <select
                    value={newProdAccountType}
                    onChange={e => setNewProdAccountType(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="preactivated">🔑 Pre-Activated Account</option>
                    <option value="existing_account">👤 Existing User Account / Upgrade</option>
                    <option value="key">🛡️ License Key / Activation Code</option>
                    <option value="invite">📩 Direct Workspace / Team Invite</option>
                  </select>
                </div>
              </div>

              {/* Highlight Toggles */}
              <div className="flex items-center gap-4 py-2 border-y border-neutral-800/60">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newProdFeatured}
                    onChange={e => setNewProdFeatured(e.target.checked)}
                    className="rounded bg-neutral-950 border-neutral-700 text-purple-600 focus:ring-0"
                  />
                  <span className="text-neutral-300 flex items-center gap-1.5">
                    <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                    <span>Featured</span>
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newProdHot}
                    onChange={e => setNewProdHot(e.target.checked)}
                    className="rounded bg-neutral-950 border-neutral-700 text-rose-600 focus:ring-0"
                  />
                  <span className="text-neutral-300 flex items-center gap-1.5">
                    <Flame className="w-3.5 h-3.5 text-rose-500" />
                    <span>Hot</span>
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newProdBestseller}
                    onChange={e => setNewProdBestseller(e.target.checked)}
                    className="rounded bg-neutral-950 border-neutral-700 text-amber-600 focus:ring-0"
                  />
                  <span className="text-neutral-300 flex items-center gap-1.5">
                    <Crown className="w-3.5 h-3.5 text-amber-400" />
                    <span>Best Seller</span>
                  </span>
                </label>
              </div>

              {/* Auto Delivery Engine Toggle & Custom Template */}
              <div className="p-3.5 bg-neutral-950/80 border border-neutral-800 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <Bolt className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Allow Automated Delivery</span>
                    </span>
                    <p className="text-[11px] text-neutral-400">Auto-order from Provider API / Stock and dispatch email with Telegram alerts</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setNewProdAutoDelivery(!newProdAutoDelivery)}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                      newProdAutoDelivery ? "bg-emerald-600" : "bg-neutral-700"
                    }`}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                        newProdAutoDelivery ? "translate-x-4" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-neutral-800/80">
                  <label className="font-semibold text-neutral-300 flex items-center justify-between text-[11px]">
                    <span>Custom Item Delivery Template (Optional)</span>
                    <span className="text-neutral-500 font-normal">Leave blank to use global template</span>
                  </label>
                  <textarea
                    rows={2}
                    value={newProdDeliveryTemplate}
                    onChange={e => setNewProdDeliveryTemplate(e.target.value)}
                    placeholder="Hello {customer_email}, here are your keys: {credentials}"
                    className="w-full px-3 py-1.5 bg-neutral-900 border border-neutral-800 rounded-xl text-white font-mono text-[11px] focus:outline-none focus:border-purple-500 leading-relaxed"
                  />
                </div>
              </div>

              {/* Initial Keys */}
              <div className="space-y-1.5">
                <label className="font-semibold text-neutral-300 flex items-center justify-between">
                  <span>Initial Stock Keys / Accounts (One per line)</span>
                  <span className="text-neutral-500 font-normal">Optional</span>
                </label>
                <textarea
                  rows={3}
                  value={newProdInitialKeys}
                  onChange={e => setNewProdInitialKeys(e.target.value)}
                  placeholder="key-12345&#10;user:password&#10;license-ABC-XYZ"
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono text-[11px] focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setIsAddProductOpen(false)}
                  className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold shadow-md shadow-purple-600/30"
                >
                  Create Product
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: BULK PRICE ADJUSTMENT */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isBulkPriceOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-3xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Percent className="w-4 h-4 text-emerald-400" />
                <span>Bulk Price Adjustment Tool</span>
              </h3>
              <button onClick={() => setIsBulkPriceOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleApplyBulkPrice} className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-semibold text-neutral-300">Target Category</label>
                <select
                  value={bulkCatId}
                  onChange={e => setBulkCatId(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                >
                  <option value="all">⚡ All Products in Store</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.id.toString()}>{c.name}</option>
                  ))}
                  <option value="999">Wholesale Reseller APIs</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Adjustment Type</label>
                  <select
                    value={bulkChangeType}
                    onChange={e => setBulkChangeType(e.target.value as any)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="percentage">Percentage (%)</option>
                    <option value="fixed_amount">Fixed USD ($)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">
                    {bulkChangeType === "percentage" ? "Percent (+10 or -5)" : "Amount (+1.00 or -0.50)"}
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder={bulkChangeType === "percentage" ? "+15" : "+1.50"}
                    value={bulkChangeValue}
                    onChange={e => setBulkChangeValue(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-neutral-300">Round To Nearest Step</label>
                <select
                  value={bulkRounding}
                  onChange={e => setBulkRounding(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                >
                  <option value={0.25}>$0.25 (e.g. $4.25, $4.50)</option>
                  <option value={0.50}>$0.50 (e.g. $4.50, $5.00)</option>
                  <option value={1.00}>$1.00 (e.g. $4.00, $5.00)</option>
                  <option value={0.01}>$0.01 (Exact Penny)</option>
                </select>
              </div>

              <div className="p-3 bg-amber-950/40 border border-amber-500/30 rounded-xl text-[11px] text-amber-200">
                ⚠️ This will update all items in the selected category immediately across the live store.
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setIsBulkPriceOpen(false)}
                  className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shadow-md shadow-emerald-600/30"
                >
                  Apply Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: STOCK & KEYS MANAGER */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isStockModalOpen && stockProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-lg rounded-3xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Key className="w-4 h-4 text-purple-400" />
                  <span>Stock Keys: {stockProduct.name}</span>
                </h3>
                <p className="text-xs text-neutral-400">{stockItems.length} unsold credentials currently in inventory</p>
              </div>
              <button onClick={() => setIsStockModalOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Existing Keys List */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-neutral-300">Current Inventory</label>
              <div className="max-h-44 overflow-y-auto bg-neutral-950 p-2.5 rounded-xl border border-neutral-800 divide-y divide-neutral-900 font-mono text-xs">
                {stockItems.length === 0 ? (
                  <div className="text-center py-4 text-neutral-600">Out of Stock. Upload keys below.</div>
                ) : (
                  stockItems.map(item => (
                    <div key={item.id} className="py-1.5 px-2 flex items-center justify-between group">
                      <span className="text-neutral-300 truncate mr-2">{item.value}</span>
                      <button
                        onClick={() => handleDeleteStockItem(item.id)}
                        className="text-neutral-600 hover:text-rose-400 opacity-0 group-hover:opacity-100 transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Bulk Add Box */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-neutral-300">Add More Keys / Accounts (One per line)</label>
              <textarea
                rows={4}
                value={newStockKeys}
                onChange={e => setNewStockKeys(e.target.value)}
                placeholder="key-ABC-123&#10;user:password&#10;netflix-access-token"
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-800">
              <button
                type="button"
                onClick={() => setIsStockModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs font-medium"
              >
                Done
              </button>
              <button
                type="button"
                onClick={handleAddStockKeys}
                disabled={!newStockKeys.trim()}
                className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold shadow-md shadow-purple-600/30"
              >
                Upload Keys
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: EDIT PRODUCT */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isEditProductOpen && editingProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-lg rounded-3xl p-6 space-y-5 my-8">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-purple-400" />
                <span>Edit Product Details</span>
              </h3>
              <button onClick={() => setIsEditProductOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEditProduct} className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-semibold text-neutral-300">Product Name</label>
                <input
                  type="text"
                  value={editingProduct.name}
                  onChange={e => setEditingProduct({ ...editingProduct, name: e.target.value })}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-neutral-300">Product Description</label>
                <textarea
                  rows={3}
                  value={editingProduct.description || ""}
                  onChange={e => setEditingProduct({ ...editingProduct, description: e.target.value })}
                  placeholder="Enter detailed description, key features, instructions..."
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500 leading-relaxed"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Price ($ USD) *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editingProduct.price}
                    onChange={e => setEditingProduct({ ...editingProduct, price: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Price (NPR रु) <span className="text-neutral-500 font-normal">Override</span></label>
                  <input
                    type="number"
                    step="1"
                    placeholder={`Auto (Rs. ${Math.round(editingProduct.price * (settings.npr_exchange_rate || 135))})`}
                    value={editingProduct.price_npr !== null && editingProduct.price_npr !== undefined ? editingProduct.price_npr : ""}
                    onChange={e => setEditingProduct({ ...editingProduct, price_npr: e.target.value ? parseFloat(e.target.value) : null })}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Cost Price ($ USD)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editingProduct.cost_price}
                    onChange={e => setEditingProduct({ ...editingProduct, cost_price: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Warranty</label>
                  <input
                    type="text"
                    value={editingProduct.warranty || ""}
                    onChange={e => setEditingProduct({ ...editingProduct, warranty: e.target.value })}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Custom Badge Text</label>
                  <input
                    type="text"
                    value={editingProduct.badge_text || ""}
                    onChange={e => setEditingProduct({ ...editingProduct, badge_text: e.target.value })}
                    placeholder="e.g. SALE"
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              {/* Delivery Mode & Account Type Selectors */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Delivery Mode</label>
                  <select
                    value={editingProduct.delivery_type || "instant"}
                    onChange={e => setEditingProduct({ ...editingProduct, delivery_type: e.target.value })}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="instant">⚡ Instant Delivery (Automated)</option>
                    <option value="manual">⏱️ Manual Dispatch (Staff / Pre-order)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-neutral-300">Account / Key Type</label>
                  <select
                    value={editingProduct.account_type || "preactivated"}
                    onChange={e => setEditingProduct({ ...editingProduct, account_type: e.target.value })}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="preactivated">🔑 Pre-Activated Account</option>
                    <option value="existing_account">👤 Existing User Account / Upgrade</option>
                    <option value="key">🛡️ License Key / Activation Code</option>
                    <option value="invite">📩 Direct Workspace / Team Invite</option>
                  </select>
                </div>
              </div>

              {/* Badges Toggles */}
              <div className="flex items-center gap-4 py-2 border-y border-neutral-800/60">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingProduct.is_featured}
                    onChange={e => setEditingProduct({ ...editingProduct, is_featured: e.target.checked })}
                    className="rounded bg-neutral-950 border-neutral-700 text-purple-600 focus:ring-0"
                  />
                  <span className="text-neutral-300 flex items-center gap-1.5">
                    <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                    <span>Featured</span>
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingProduct.is_hot}
                    onChange={e => setEditingProduct({ ...editingProduct, is_hot: e.target.checked })}
                    className="rounded bg-neutral-950 border-neutral-700 text-rose-600 focus:ring-0"
                  />
                  <span className="text-neutral-300 flex items-center gap-1.5">
                    <Flame className="w-3.5 h-3.5 text-rose-500" />
                    <span>Hot</span>
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingProduct.is_bestseller}
                    onChange={e => setEditingProduct({ ...editingProduct, is_bestseller: e.target.checked })}
                    className="rounded bg-neutral-950 border-neutral-700 text-amber-600 focus:ring-0"
                  />
                  <span className="text-neutral-300 flex items-center gap-1.5">
                    <Crown className="w-3.5 h-3.5 text-amber-400" />
                    <span>Best Seller</span>
                  </span>
                </label>
              </div>

              {/* Auto Delivery Engine Toggle & Custom Template */}
              <div className="p-3.5 bg-neutral-950/80 border border-neutral-800 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <Bolt className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Allow Automated Delivery</span>
                    </span>
                    <p className="text-[11px] text-neutral-400">Auto-order from Provider API / Stock and dispatch email with Telegram alerts</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEditingProduct({ ...editingProduct, auto_delivery: !(editingProduct.auto_delivery !== false) })}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                      editingProduct.auto_delivery !== false ? "bg-emerald-600" : "bg-neutral-700"
                    }`}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                        editingProduct.auto_delivery !== false ? "translate-x-4" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-neutral-800/80">
                  <label className="font-semibold text-neutral-300 flex items-center justify-between text-[11px]">
                    <span>Item Delivery Message Template</span>
                    <span className="text-neutral-500 font-normal">Leave blank to use global template</span>
                  </label>
                  <textarea
                    rows={3}
                    value={editingProduct.delivery_template || ""}
                    onChange={e => setEditingProduct({ ...editingProduct, delivery_template: e.target.value })}
                    placeholder="Hello {customer_email}, here are your keys: {credentials}"
                    className="w-full px-3 py-1.5 bg-neutral-900 border border-neutral-800 rounded-xl text-white font-mono text-[11px] focus:outline-none focus:border-purple-500 leading-relaxed"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setIsEditProductOpen(false)}
                  className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: BALANCE ADJUSTMENT */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isBalanceModalOpen && balanceUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-sm rounded-3xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-white">Adjust Customer Balance</h3>
              <button onClick={() => setIsBalanceModalOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-neutral-400">
              Customer: <span className="text-white font-semibold">{balanceUser.email || balanceUser.telegram_id}</span>
              <br />
              Current Balance: <span className="text-emerald-400 font-mono font-bold">${balanceUser.balance.toFixed(2)}</span>
            </div>

            <form onSubmit={handleAdjustBalance} className="space-y-3 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-neutral-300">Adjustment Amount (USD)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  placeholder="+10.00 or -5.00"
                  value={balanceAmount}
                  onChange={e => setBalanceAmount(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-neutral-300">Reason</label>
                <input
                  type="text"
                  value={balanceReason}
                  onChange={e => setBalanceReason(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsBalanceModalOpen(false)}
                  className="px-3.5 py-1.5 rounded-xl bg-neutral-800 text-neutral-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-xl bg-emerald-600 text-white font-semibold"
                >
                  Confirm Adjustment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: ORDER CREDENTIALS VIEWER */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isOrderCredentialsOpen && selectedOrderCredentials && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-3xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Key className="w-4 h-4 text-purple-400" />
                <span>Delivered Keys & Credentials</span>
              </h3>
              <button onClick={() => setIsOrderCredentialsOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-neutral-950 rounded-xl border border-neutral-800 font-mono text-xs text-purple-200 whitespace-pre-wrap max-h-60 overflow-y-auto select-all">
              {selectedOrderCredentials}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(selectedOrderCredentials);
                  showToast("Credentials copied to clipboard!");
                }}
                className="px-4 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold flex items-center gap-1.5"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copy Credentials</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: NEW CATEGORY */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isAddCategoryOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-sm rounded-3xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-white">Create New Category</h3>
              <button onClick={() => setIsAddCategoryOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateCategory} className="space-y-3 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-neutral-300">Category Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. VPN Services"
                  value={newCatName}
                  onChange={e => setNewCatName(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddCategoryOpen(false)}
                  className="px-3.5 py-1.5 rounded-xl bg-neutral-800 text-neutral-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-xl bg-purple-600 text-white font-semibold"
                >
                  Create Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: EDIT CATEGORY */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isEditCategoryOpen && editingCategory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-sm rounded-3xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-white">Rename Category</h3>
              <button onClick={() => setIsEditCategoryOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEditCategory} className="space-y-3 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-neutral-300">Category Name</label>
                <input
                  type="text"
                  required
                  value={editingCategory.name}
                  onChange={e => setEditingCategory({ ...editingCategory, name: e.target.value })}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsEditCategoryOpen(false)}
                  className="px-3.5 py-1.5 rounded-xl bg-neutral-800 text-neutral-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-xl bg-purple-600 text-white font-semibold"
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: USER PURCHASES HISTORY & DELIVERED CREDENTIALS */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isUserPurchasesOpen && userPurchasesUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-2xl rounded-3xl p-6 space-y-5 my-8 shadow-2xl">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Package className="w-4 h-4 text-purple-400" />
                  <span>Purchases Ledger: {userPurchasesUser.email || `User #${userPurchasesUser.telegram_id}`}</span>
                </h3>
                <p className="text-xs text-neutral-400 font-mono mt-0.5">
                  Telegram ID: {userPurchasesUser.telegram_id} • Balance: ${userPurchasesUser.balance.toFixed(2)}
                </p>
              </div>
              <button onClick={() => setIsUserPurchasesOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            {loadingUserPurchases ? (
              <div className="py-12 flex flex-col items-center justify-center text-neutral-400">
                <RefreshCw className="w-8 h-8 animate-spin text-purple-500 mb-2" />
                <span className="text-xs">Loading customer purchase ledger...</span>
              </div>
            ) : userPurchasesList.length === 0 ? (
              <div className="py-12 text-center text-neutral-500 text-xs">
                No purchases recorded for this customer yet.
              </div>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-3 pr-1">
                {userPurchasesList.map(item => (
                  <div key={item.id} className="bg-neutral-950 p-4 rounded-2xl border border-neutral-800 space-y-2.5">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="font-bold text-white text-xs">{item.item_name}</div>
                        <div className="text-[10px] text-neutral-500 font-mono">
                          Order ID: #{item.unique_id} • {new Date(item.bought_datetime).toLocaleString()}
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-bold font-mono text-emerald-400">${item.price.toFixed(2)}</span>
                        <span className="text-[10px] text-neutral-500 block font-mono">Cost: ${item.cost_price.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px] text-neutral-400 font-mono">
                        <span>Delivered Credentials / Key:</span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(item.value);
                            showToast("Copied credentials to clipboard!");
                          }}
                          className="flex items-center gap-1 text-purple-400 hover:text-purple-300 font-sans"
                        >
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </button>
                      </div>
                      <pre className="p-2.5 bg-neutral-900 border border-neutral-800/80 rounded-xl text-emerald-300 font-mono text-xs overflow-x-auto whitespace-pre-wrap select-all">
                        {item.value || "Delivered instantly"}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-neutral-800 text-xs">
              <span className="text-neutral-500 font-mono">Total {userPurchasesList.length} items purchased</span>
              <button
                type="button"
                onClick={() => setIsUserPurchasesOpen(false)}
                className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL: RESELLER TOP-UP RECORD */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isTopUpModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-neutral-900 border border-neutral-800 w-full max-w-md rounded-3xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Wallet className="w-4 h-4 text-emerald-400" />
                <span>Record Reseller API Deposit / Top-up</span>
              </h3>
              <button onClick={() => setIsTopUpModalOpen(false)} className="text-neutral-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRecordTopUp} className="space-y-3.5 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-neutral-300">API Provider *</label>
                <select
                  value={topUpSourceId}
                  onChange={e => setTopUpSourceId(parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500 uppercase font-mono"
                >
                  {resellerBudget?.balances.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name} (Current Bal: ${s.balance.toFixed(2)})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-semibold text-neutral-300">Amount ($ USD) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="50.00"
                    value={topUpAmount}
                    onChange={e => setTopUpAmount(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-semibold text-neutral-300">Payment Method</label>
                  <input
                    type="text"
                    value={topUpMethod}
                    onChange={e => setTopUpMethod(e.target.value)}
                    placeholder="USDT TRC20"
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-neutral-300">Note / Reference</label>
                <input
                  type="text"
                  value={topUpNote}
                  onChange={e => setTopUpNote(e.target.value)}
                  placeholder="e.g. Binance Pay Transfer for Claude Keys"
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-neutral-300">Tx Hash / Proof (Optional)</label>
                <input
                  type="text"
                  value={topUpTxHash}
                  onChange={e => setTopUpTxHash(e.target.value)}
                  placeholder="0x... or Tx ID"
                  className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-xl text-white font-mono focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setIsTopUpModalOpen(false)}
                  className="px-3.5 py-1.5 rounded-xl bg-neutral-800 text-neutral-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shadow-md shadow-emerald-600/30"
                >
                  Save & Update Balance
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
