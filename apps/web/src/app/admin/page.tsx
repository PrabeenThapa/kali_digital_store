"use client";

import { useEffect, useState, useMemo } from "react";
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
} from "lucide-react";

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

interface AdminProduct {
  id: number;
  name: string;
  category_id: number;
  category_name: string;
  price: number;
  cost_price: number;
  stock: number;
  is_featured: boolean;
  warranty: string | null;
  note: string | null;
  source_type: string;
}

interface AdminCategory {
  id: number;
  name: string;
  is_active: boolean;
  products_count: number;
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
  amount: number;
  currency: string;
  status: string;
  created_at: string;
}

interface AdminAuditLog {
  id: number;
  timestamp: string;
  level: string;
  user_id: number | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: string | null;
}

type TabType = "overview" | "users" | "products" | "promocodes" | "orders" | "payments" | "nepal_qr" | "audit";

export default function AdminPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  // Nepal QR Config & Coming Soon Banner state
  const [nepalQrUrl, setNepalQrUrl] = useState("");
  const [nepalQrTitle, setNepalQrTitle] = useState("eSewa / Khalti / Fonepay Direct QR");
  const [nepalQrAccountName, setNepalQrAccountName] = useState("Kali Store Nepal");
  const [nepalQrAccountId, setNepalQrAccountId] = useState("9800000000");
  const [nepalQrInstructions, setNepalQrInstructions] = useState("Scan QR code with eSewa/Khalti/Fonepay, transfer exact NPR amount, then submit your Tx Reference ID below.");
  const [nepalComingSoon, setNepalComingSoon] = useState(true);
  const [nepalComingSoonText, setNepalComingSoonText] = useState("🇳🇵 Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon! Stay tuned as we roll out instant eSewa & Khalti automated API verification.");
  const [isSavingNepalQr, setIsSavingNepalQr] = useState(false);
  const [nepalQrSaveSuccess, setNepalQrSaveSuccess] = useState(false);

  // Product Creation & Keys Modal State
  const [isAddProductOpen, setIsAddProductOpen] = useState(false);
  const [newProdName, setNewProdName] = useState("");
  const [newProdCatId, setNewProdCatId] = useState<number>(0);
  const [newProdPrice, setNewProdPrice] = useState("");
  const [newProdCostPrice, setNewProdCostPrice] = useState("");
  const [newProdWarranty, setNewProdWarranty] = useState("24 Hours");
  const [newProdNote, setNewProdNote] = useState("");
  const [newProdKeys, setNewProdKeys] = useState("");

  const [addKeysProduct, setAddKeysProduct] = useState<AdminProduct | null>(null);
  const [stockKeysInput, setStockKeysInput] = useState("");

  // Category Modal State
  const [isAddCategoryOpen, setIsAddCategoryOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");

  // Promocode State
  const [promocodes, setPromocodes] = useState<any[]>([]);
  const [isAddPromoOpen, setIsAddPromoOpen] = useState(false);
  const [newPromoCode, setNewPromoCode] = useState("");
  const [newPromoType, setNewPromoType] = useState("percent");
  const [newPromoValue, setNewPromoValue] = useState("");
  const [newPromoMaxUses, setNewPromoMaxUses] = useState("100");
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const fetchNepalQrSettings = async () => {
    try {
      const res = await api.get('/admin/nepal-qr');
      if (res.data) {
        setNepalQrUrl(res.data.qr_url || "");
        setNepalQrTitle(res.data.title || "eSewa / Khalti / Fonepay Direct QR");
        setNepalQrAccountName(res.data.account_name || "Kali Store Nepal");
        setNepalQrAccountId(res.data.account_id || "9800000000");
        setNepalQrInstructions(res.data.instructions || "");
        setNepalComingSoon(res.data.coming_soon ?? true);
        if (res.data.coming_soon_text) setNepalComingSoonText(res.data.coming_soon_text);
      }
    } catch (e) {
      console.error("Failed to load Nepal QR settings", e);
    }
  };

  const handleSaveNepalQr = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingNepalQr(true);
    try {
      await api.post('/admin/nepal-qr', {
        qr_url: nepalQrUrl,
        title: nepalQrTitle,
        account_name: nepalQrAccountName,
        account_id: nepalQrAccountId,
        instructions: nepalQrInstructions,
        coming_soon: nepalComingSoon,
        coming_soon_text: nepalComingSoonText,
      });
      setNepalQrSaveSuccess(true);
      setTimeout(() => setNepalQrSaveSuccess(false), 3000);
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to save Nepal QR settings.");
    } finally {
      setIsSavingNepalQr(false);
    }
  };

  const fetchPromocodes = async () => {
    try {
      const res = await api.get('/admin/promocodes');
      setPromocodes(res.data || []);
    } catch (e) {
      console.error("Failed to load promocodes", e);
    }
  };

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProdName.trim() || !newProdPrice || !newProdCatId) {
      alert("Please fill in Product Name, Price, and Category.");
      return;
    }
    try {
      await api.post('/admin/products', {
        name: newProdName,
        category_id: newProdCatId,
        price: parseFloat(newProdPrice),
        cost_price: parseFloat(newProdCostPrice || "0"),
        warranty: newProdWarranty,
        note: newProdNote,
        initial_keys: newProdKeys,
      });
      alert("Product created successfully!");
      setIsAddProductOpen(false);
      setNewProdName("");
      setNewProdPrice("");
      setNewProdCostPrice("");
      setNewProdKeys("");
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to create product.");
    }
  };

  const handleDeleteProduct = async (prodId: number) => {
    if (!confirm("Are you sure you want to delete this product and its unsold keys?")) return;
    try {
      await api.delete(`/admin/products/${prodId}`);
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to delete product.");
    }
  };

  const handleAddStockKeys = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addKeysProduct || !stockKeysInput.trim()) return;
    try {
      const res = await api.post(`/admin/products/${addKeysProduct.id}/keys`, {
        keys: stockKeysInput,
      });
      alert(`Added ${res.data.added_count} new keys to stock!`);
      setAddKeysProduct(null);
      setStockKeysInput("");
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to add keys.");
    }
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCategoryName.trim()) return;
    try {
      await api.post('/admin/categories', { name: newCategoryName });
      setIsAddCategoryOpen(false);
      setNewCategoryName("");
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to create category.");
    }
  };

  const handleDeleteCategory = async (catId: number) => {
    if (!confirm("Are you sure you want to delete this category?")) return;
    try {
      await api.delete(`/admin/categories/${catId}`);
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to delete category.");
    }
  };

  const handleCreatePromo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPromoCode.trim() || !newPromoValue) return;
    try {
      await api.post('/admin/promocodes', {
        code: newPromoCode,
        discount_type: newPromoType,
        discount_value: parseFloat(newPromoValue),
        max_uses: parseInt(newPromoMaxUses || "0"),
      });
      setIsAddPromoOpen(false);
      setNewPromoCode("");
      setNewPromoValue("");
      fetchPromocodes();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to create promocode.");
    }
  };

  const handleDeletePromo = async (promoId: number) => {
    if (!confirm("Delete this promocode?")) return;
    try {
      await api.delete(`/admin/promocodes/${promoId}`);
      fetchPromocodes();
    } catch (err: any) {
      alert("Failed to delete promocode.");
    }
  };

  const handleApprovePayment = async (paymentId: number) => {
    if (!confirm(`Approve payment #${paymentId} and credit user balance?`)) return;
    try {
      const res = await api.post(`/admin/payments/${paymentId}/approve`);
      alert(res.data.message || "Payment approved!");
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to approve payment.");
    }
  };

  const handleRejectPayment = async (paymentId: number) => {
    if (!confirm(`Reject payment #${paymentId}?`)) return;
    try {
      await api.post(`/admin/payments/${paymentId}/reject`);
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to reject payment.");
    }
  };

  // Data states
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [payments, setPayments] = useState<AdminPayment[]>([]);
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([]);

  // Search & Filter states
  const [userSearch, setUserSearch] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [orderSearch, setOrderSearch] = useState("");
  const [paymentSearch, setPaymentSearch] = useState("");
  const [paymentProviderFilter, setPaymentProviderFilter] = useState("all");
  const [auditSearch, setAuditSearch] = useState("");

  // Modal / Interaction states
  const [selectedSecret, setSelectedSecret] = useState<{ title: string; content: string } | null>(null);
  const [balanceModalUser, setBalanceModalUser] = useState<AdminUser | null>(null);
  const [balanceAdjustAmount, setBalanceAdjustAmount] = useState("");
  const [balanceAdjustReason, setBalanceAdjustReason] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const loadAdminData = async () => {
    setRefreshing(true);
    try {
      // 1. Verify current user profile & admin status
      const meRes = await api.get("/user/me");
      if (!meRes.data?.is_admin) {
        alert("Access denied: Admin privileges required.");
        router.push("/dashboard");
        return;
      }
      setIsAdmin(true);

      // 2. Fetch all admin datasets concurrently
      const [
        statsRes,
        usersRes,
        productsRes,
        categoriesRes,
        ordersRes,
        paymentsRes,
        auditRes,
      ] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/users?limit=100"),
        api.get("/admin/products?limit=200"),
        api.get("/admin/categories"),
        api.get("/admin/orders?limit=100"),
        api.get("/admin/payments?limit=100"),
        api.get("/admin/audit-logs?limit=100"),
      ]);

      setStats(statsRes.data);
      setUsers(usersRes.data);
      setProducts(productsRes.data);
      setCategories(categoriesRes.data);
      setOrders(ordersRes.data);
      setPayments(paymentsRes.data);
      setAuditLogs(auditRes.data);
    } catch (err: any) {
      console.error("Failed to load admin data:", err);
      if (err.response?.status === 403 || err.response?.status === 401) {
        alert("Admin authorization failed. Please log in with an admin account.");
        router.push("/login");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    // Theme init
    const savedTheme = (localStorage.getItem("theme") as "dark" | "light") || "dark";
    setTheme(savedTheme);
    if (savedTheme === "light") document.documentElement.classList.add("light-theme");
    else document.documentElement.classList.remove("light-theme");

    loadAdminData();
  }, [router]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("theme", next);
    if (next === "light") document.documentElement.classList.add("light-theme");
    else document.documentElement.classList.remove("light-theme");
  };

  // Actions
  const handleBalanceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!balanceModalUser) return;
    const amt = parseFloat(balanceAdjustAmount);
    if (isNaN(amt) || amt === 0) {
      alert("Please enter a valid non-zero amount.");
      return;
    }

    try {
      const res = await api.post(`/admin/users/${balanceModalUser.telegram_id}/balance`, {
        amount: amt,
        reason: balanceAdjustReason || "Manual adjustment via Admin Panel",
      });
      alert(`Success! New balance: $${res.data.new_balance.toFixed(2)}`);
      setBalanceModalUser(null);
      setBalanceAdjustAmount("");
      setBalanceAdjustReason("");
      loadAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to adjust balance.");
    }
  };

  const handleToggleBlock = async (user: AdminUser) => {
    const action = user.is_blocked ? "unblock" : "block";
    if (!confirm(`Are you sure you want to ${action} user ${user.email || user.telegram_id}?`)) return;

    try {
      await api.post(`/admin/users/${user.telegram_id}/toggle-block`);
      loadAdminData();
    } catch (err) {
      alert("Failed to update user block status.");
    }
  };

  const handleToggleFeatured = async (product: AdminProduct) => {
    try {
      await api.post(`/admin/products/${product.id}/toggle-featured`);
      loadAdminData();
    } catch (err) {
      alert("Failed to toggle featured status.");
    }
  };

  const handleToggleCategory = async (cat: AdminCategory) => {
    try {
      await api.post(`/admin/categories/${cat.id}/toggle-active`);
      loadAdminData();
    } catch (err) {
      alert("Failed to toggle category active status.");
    }
  };

  // Filtered lists
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const q = userSearch.toLowerCase().trim();
      if (!q) return true;
      return (
        u.telegram_id.toString().includes(q) ||
        (u.email && u.email.toLowerCase().includes(q)) ||
        u.role_name.toLowerCase().includes(q)
      );
    });
  }, [users, userSearch]);

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const q = productSearch.toLowerCase().trim();
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.category_name.toLowerCase().includes(q)
      );
    });
  }, [products, productSearch]);

  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      const q = orderSearch.toLowerCase().trim();
      if (!q) return true;
      return (
        o.item_name.toLowerCase().includes(q) ||
        (o.buyer_id && o.buyer_id.toString().includes(q)) ||
        (o.buyer_email && o.buyer_email.toLowerCase().includes(q)) ||
        o.unique_id.toString().includes(q)
      );
    });
  }, [orders, orderSearch]);

  const filteredPayments = useMemo(() => {
    return payments.filter((p) => {
      if (paymentProviderFilter !== "all" && p.provider !== paymentProviderFilter) return false;
      const q = paymentSearch.toLowerCase().trim();
      if (!q) return true;
      return (
        p.external_id.toLowerCase().includes(q) ||
        p.provider.toLowerCase().includes(q) ||
        (p.user_id && p.user_id.toString().includes(q))
      );
    });
  }, [payments, paymentSearch, paymentProviderFilter]);

  const filteredAuditLogs = useMemo(() => {
    return auditLogs.filter((l) => {
      const q = auditSearch.toLowerCase().trim();
      if (!q) return true;
      return (
        l.action.toLowerCase().includes(q) ||
        (l.details && l.details.toLowerCase().includes(q)) ||
        (l.user_id && l.user_id.toString().includes(q))
      );
    });
  }, [auditLogs, auditSearch]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-muted-foreground text-sm font-medium">Loading Admin Control Center...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col md:flex-row">
      {/* Admin Sidebar */}
      <aside className="w-full md:w-64 glass border-r border-border/50 md:h-screen sticky top-0 flex flex-col z-20">
        <div className="p-6">
          {/* Logo */}
          <Link href="/store" className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-lg shadow-primary/30">
              <Bolt className="w-4 h-4 text-white" />
            </div>
            <span className="font-extrabold text-[15px] tracking-tight">KDS <span className="text-primary">Admin</span></span>
          </Link>
          {/* Back to Store */}
          <Link href="/store" className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-primary transition-colors mb-6 group">
            <ArrowLeft className="w-3 h-3 group-hover:-translate-x-0.5 transition-transform" />
            Back to Store
          </Link>

          <nav className="space-y-1.5">
            <button
              onClick={() => setActiveTab("overview")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${
                activeTab === "overview"
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              Overview
            </button>

            <button
              onClick={() => setActiveTab("users")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${
                activeTab === "users"
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <Users className="w-4 h-4" />
              Users Directory
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-background/30">
                {users.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab("products")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${
                activeTab === "products"
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <Package className="w-4 h-4" />
              Products & Stock
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-background/30">
                {products.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab("orders")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${
                activeTab === "orders"
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <ShoppingCart className="w-4 h-4" />
              Orders & Sales
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-background/30">
                {orders.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab("payments")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${
                activeTab === "payments"
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <CreditCard className="w-4 h-4" />
              Transactions & TxID
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-background/30">
                {payments.length}
              </span>
            </button>

            <button
              onClick={() => {
                setActiveTab("nepal_qr");
                fetchNepalQrSettings();
              }}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${
                activeTab === "nepal_qr"
                  ? "bg-red-500 text-white shadow-lg shadow-red-500/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <Sparkles className="w-4 h-4 text-amber-300" />
              🇳🇵 Nepal QR Upload
            </button>

            <button
              onClick={() => setActiveTab("audit")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${
                activeTab === "audit"
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <ShieldAlert className="w-4 h-4" />
              Audit Logs
            </button>
          </nav>
        </div>

        <div className="mt-auto p-6 border-t border-border/40 space-y-2">
          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-colors text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            {theme === "dark"
              ? <><Sun className="w-4 h-4 text-amber-400" /> Light Mode</>
              : <><Moon className="w-4 h-4 text-indigo-400" /> Dark Mode</>}
          </button>
          <Link
            href="/dashboard"
            className="w-full flex items-center gap-3 px-4 py-2.5 text-muted-foreground hover:text-foreground hover:bg-accent rounded-xl transition-colors text-sm font-medium"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Dashboard
          </Link>
          <Link
            href="/store"
            className="w-full flex items-center gap-3 px-4 py-2.5 text-muted-foreground hover:text-foreground hover:bg-accent rounded-xl transition-colors text-sm font-medium"
          >
            <ExternalLink className="w-4 h-4" /> View Live Store
          </Link>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-6 md:p-10 overflow-y-auto max-w-7xl">
        {/* Top bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight capitalize">
              {activeTab === "overview" && "Dashboard Overview"}
              {activeTab === "users" && "Users Directory & Balances"}
              {activeTab === "products" && "Product Catalog & Inventory"}
              {activeTab === "orders" && "Sales & Delivered Orders"}
              {activeTab === "payments" && "Payment Gateway Transactions"}
              {activeTab === "audit" && "Security & Audit Trail"}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Live automated data sync across Telegram bot and web platform.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadAdminData}
              disabled={refreshing}
              className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 text-secondary-foreground text-sm font-semibold rounded-xl border border-border transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-primary" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh Data"}
            </button>
          </div>
        </div>

        {/* ── TAB 1: OVERVIEW ──────────────────────────────────────────────── */}
        {activeTab === "overview" && stats && (
          <div className="space-y-8 animate-in fade-in duration-300">
            {/* Stat metric cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {/* Total Revenue */}
              <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-28 h-28 bg-emerald-500/10 rounded-full blur-[32px] -translate-y-1/2 translate-x-1/2" />
                <div className="flex items-center justify-between text-muted-foreground mb-3">
                  <span className="text-sm font-medium">Total Revenue</span>
                  <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
                    <DollarSign className="w-5 h-5" />
                  </div>
                </div>
                <h3 className="text-3xl font-bold">${stats.total_sales_usd.toFixed(2)}</h3>
                <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                  <span className="text-emerald-400 font-semibold">+${stats.sales_today_usd.toFixed(2)}</span> today
                </p>
              </div>

              {/* Net Profit */}
              <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-28 h-28 bg-primary/15 rounded-full blur-[32px] -translate-y-1/2 translate-x-1/2" />
                <div className="flex items-center justify-between text-muted-foreground mb-3">
                  <span className="text-sm font-medium">Net Profit</span>
                  <div className="p-2 rounded-xl bg-primary/10 text-primary">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                </div>
                <h3 className="text-3xl font-bold">${stats.total_profit_usd.toFixed(2)}</h3>
                <p className="text-xs text-muted-foreground mt-2">
                  Margin: {stats.total_sales_usd > 0 ? ((stats.total_profit_usd / stats.total_sales_usd) * 100).toFixed(1) : 0}%
                </p>
              </div>

              {/* Total Orders */}
              <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-28 h-28 bg-blue-500/10 rounded-full blur-[32px] -translate-y-1/2 translate-x-1/2" />
                <div className="flex items-center justify-between text-muted-foreground mb-3">
                  <span className="text-sm font-medium">Total Orders</span>
                  <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
                    <ShoppingCart className="w-5 h-5" />
                  </div>
                </div>
                <h3 className="text-3xl font-bold">{stats.total_orders}</h3>
                <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                  <span className="text-blue-400 font-semibold">+{stats.orders_today}</span> completed today
                </p>
              </div>

              {/* Registered Users */}
              <div className="glass-card p-6 rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-28 h-28 bg-purple-500/10 rounded-full blur-[32px] -translate-y-1/2 translate-x-1/2" />
                <div className="flex items-center justify-between text-muted-foreground mb-3">
                  <span className="text-sm font-medium">Total Users</span>
                  <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
                    <Users className="w-5 h-5" />
                  </div>
                </div>
                <h3 className="text-3xl font-bold">{stats.total_users}</h3>
                <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                  <span className="text-purple-400 font-semibold">+{stats.new_users_today}</span> joined today
                </p>
              </div>
            </div>

            {/* Sub stats row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="glass-card p-6 rounded-2xl flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Active Catalog Items</p>
                  <h4 className="text-2xl font-bold mt-1">{stats.total_products} items</h4>
                  <p className="text-xs text-muted-foreground mt-1">
                    {stats.in_stock_products} products with ready stock
                  </p>
                </div>
                <div className="p-3 rounded-2xl bg-secondary text-primary">
                  <Package className="w-6 h-6" />
                </div>
              </div>

              <div className="glass-card p-6 rounded-2xl flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Successful Top-Up Volume</p>
                  <h4 className="text-2xl font-bold mt-1">${stats.succeeded_payments_volume.toFixed(2)}</h4>
                  <p className="text-xs text-muted-foreground mt-1">All crypto & Bybit deposits</p>
                </div>
                <div className="p-3 rounded-2xl bg-secondary text-emerald-400">
                  <CreditCard className="w-6 h-6" />
                </div>
              </div>

              <div className="glass-card p-6 rounded-2xl flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Pending Verifications</p>
                  <h4 className="text-2xl font-bold mt-1">{stats.pending_payments} pending</h4>
                  <p className="text-xs text-muted-foreground mt-1">Awaiting confirmation or review</p>
                </div>
                <div className="p-3 rounded-2xl bg-secondary text-amber-400">
                  <Clock className="w-6 h-6" />
                </div>
              </div>
            </div>

            {/* Quick Recent Activity Columns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Orders */}
              <div className="glass-card p-6 rounded-2xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold">Recent Purchases</h3>
                  <button
                    onClick={() => setActiveTab("orders")}
                    className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
                  >
                    View all <ArrowUpRight className="w-3 h-3" />
                  </button>
                </div>
                <div className="space-y-3">
                  {orders.slice(0, 5).map((o) => (
                    <div key={o.id} className="p-3 rounded-xl bg-secondary/50 flex items-center justify-between text-sm">
                      <div>
                        <p className="font-semibold text-foreground">{o.item_name}</p>
                        <p className="text-xs text-muted-foreground">
                          Buyer: {o.buyer_email || o.buyer_id} · {new Date(o.bought_datetime).toLocaleDateString()}
                        </p>
                      </div>
                      <span className="font-bold text-emerald-400">${o.price.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recent Payments */}
              <div className="glass-card p-6 rounded-2xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold">Recent Top-Ups</h3>
                  <button
                    onClick={() => setActiveTab("payments")}
                    className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
                  >
                    View all <ArrowUpRight className="w-3 h-3" />
                  </button>
                </div>
                <div className="space-y-3">
                  {payments.slice(0, 5).map((p) => (
                    <div key={p.id} className="p-3 rounded-xl bg-secondary/50 flex items-center justify-between text-sm">
                      <div>
                        <p className="font-semibold text-foreground uppercase tracking-wider text-xs">
                          {p.provider} · <span className="text-muted-foreground font-mono text-xs">{p.external_id.slice(0, 16)}...</span>
                        </p>
                        <p className="text-xs text-muted-foreground">User: {p.user_id}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-primary">${p.amount.toFixed(2)}</p>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            p.status === "succeeded"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : p.status === "pending"
                              ? "bg-amber-500/10 text-amber-400"
                              : "bg-destructive/10 text-destructive"
                          }`}
                        >
                          {p.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 2: USERS DIRECTORY ───────────────────────────────────────── */}
        {activeTab === "users" && (
          <div className="space-y-6 animate-in fade-in duration-300">
            {/* Search toolbar */}
            <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
              <div className="relative w-full sm:w-80">
                <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search Telegram ID, email, role..."
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  className="w-full bg-secondary/60 border border-border/80 rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                />
              </div>
              <p className="text-xs text-muted-foreground font-medium">
                Showing {filteredUsers.length} of {users.length} users
              </p>
            </div>

            {/* Users Table */}
            <div className="glass-card rounded-2xl overflow-hidden border border-border/50">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-secondary/70 border-b border-border/60 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 font-semibold">User / ID</th>
                      <th className="px-5 py-3 font-semibold">Role</th>
                      <th className="px-5 py-3 font-semibold">Balance</th>
                      <th className="px-5 py-3 font-semibold">Purchases</th>
                      <th className="px-5 py-3 font-semibold">Discount</th>
                      <th className="px-5 py-3 font-semibold">Joined</th>
                      <th className="px-5 py-3 font-semibold">Status</th>
                      <th className="px-5 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {filteredUsers.map((u) => (
                      <tr key={u.telegram_id} className="hover:bg-accent/40 transition-colors">
                        <td className="px-5 py-4">
                          <div className="font-semibold text-foreground">{u.email || `User #${u.telegram_id}`}</div>
                          <div className="text-xs text-muted-foreground font-mono">ID: {u.telegram_id}</div>
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                              u.role_name === "OWNER"
                                ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                                : u.role_name === "ADMIN"
                                ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                : "bg-secondary text-muted-foreground"
                            }`}
                          >
                            {u.role_name}
                          </span>
                        </td>
                        <td className="px-5 py-4 font-bold text-foreground">
                          ${u.balance.toFixed(2)}
                        </td>
                        <td className="px-5 py-4">
                          <span className="font-medium text-foreground">{u.purchases_count}</span>
                          <span className="text-xs text-muted-foreground ml-1">(${u.total_spent.toFixed(2)})</span>
                        </td>
                        <td className="px-5 py-4">
                          {u.discount_percent > 0 ? (
                            <span className="text-primary font-bold">{u.discount_percent}%</span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-5 py-4 text-xs text-muted-foreground">
                          {u.registration_date ? new Date(u.registration_date).toLocaleDateString() : "—"}
                        </td>
                        <td className="px-5 py-4">
                          {u.is_blocked ? (
                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-destructive/15 text-destructive">
                              Blocked
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400">
                              Active
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => setBalanceModalUser(u)}
                              className="px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg text-xs font-bold transition-colors flex items-center gap-1.5"
                            >
                              <Edit3 className="w-3.5 h-3.5" /> Adjust Balance
                            </button>
                            <button
                              onClick={() => handleToggleBlock(u)}
                              className={`p-1.5 rounded-lg text-xs transition-colors ${
                                u.is_blocked
                                  ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                                  : "bg-destructive/10 text-destructive hover:bg-destructive/20"
                              }`}
                              title={u.is_blocked ? "Unblock user" : "Block user"}
                            >
                              {u.is_blocked ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
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

        {/* ── TAB 3: PRODUCTS & CATALOG ────────────────────────────────────── */}
        {activeTab === "products" && (
          <div className="space-y-8 animate-in fade-in duration-300">
            {/* Categories section */}
            <div className="glass-card p-6 rounded-2xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold flex items-center gap-2">
                  <Layers className="w-5 h-5 text-primary" /> Store Categories
                </h3>
                <button
                  onClick={() => setIsAddCategoryOpen(true)}
                  className="px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary font-bold text-xs rounded-xl transition-all"
                >
                  + Add Category
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                {categories.map((cat) => (
                  <div
                    key={cat.id}
                    className="p-4 rounded-xl bg-secondary/50 border border-border/50 flex items-center justify-between"
                  >
                    <div>
                      <h4 className="font-bold text-sm text-foreground">{cat.name}</h4>
                      <p className="text-xs text-muted-foreground mt-0.5">{cat.products_count} items</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleCategory(cat)}
                        className={`px-2.5 py-1 rounded-full text-xs font-bold transition-colors ${
                          cat.is_active
                            ? "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25"
                            : "bg-muted text-muted-foreground hover:bg-muted/80"
                        }`}
                      >
                        {cat.is_active ? "Active" : "Disabled"}
                      </button>
                      <button
                        onClick={() => handleDeleteCategory(cat.id)}
                        className="text-xs text-rose-400 hover:text-rose-300 p-1"
                        title="Delete category"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Products table */}
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
                <div className="relative w-full sm:w-80">
                  <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search product name or category..."
                    value={productSearch}
                    onChange={(e) => setProductSearch(e.target.value)}
                    className="w-full bg-secondary/60 border border-border/80 rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      if (categories.length > 0) setNewProdCatId(categories[0].id);
                      setIsAddProductOpen(true);
                    }}
                    className="px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs rounded-xl shadow-lg shadow-primary/20 transition-all flex items-center gap-1.5"
                  >
                    + Add New Product
                  </button>
                  <p className="text-xs text-muted-foreground font-medium">
                    {filteredProducts.length} items
                  </p>
                </div>
              </div>

              <div className="glass-card rounded-2xl overflow-hidden border border-border/50">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-secondary/70 border-b border-border/60 text-xs uppercase text-muted-foreground">
                      <tr>
                        <th className="px-5 py-3 font-semibold">Product Name</th>
                        <th className="px-5 py-3 font-semibold">Category</th>
                        <th className="px-5 py-3 font-semibold">Sell Price</th>
                        <th className="px-5 py-3 font-semibold">Cost Price</th>
                        <th className="px-5 py-3 font-semibold">Margin</th>
                        <th className="px-5 py-3 font-semibold">Stock / Values</th>
                        <th className="px-5 py-3 font-semibold">Featured</th>
                        <th className="px-5 py-3 font-semibold text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                      {filteredProducts.map((p) => {
                        const margin =
                          p.price > 0 ? (((p.price - p.cost_price) / p.price) * 100).toFixed(0) : "0";
                        return (
                          <tr key={p.id} className="hover:bg-accent/40 transition-colors">
                            <td className="px-5 py-4 font-bold text-foreground">
                              {p.name}
                              {p.warranty && (
                                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-normal">
                                  {p.warranty}
                                </span>
                              )}
                            </td>
                            <td className="px-5 py-4 text-muted-foreground">{p.category_name}</td>
                            <td className="px-5 py-4 font-bold text-primary">${p.price.toFixed(2)}</td>
                            <td className="px-5 py-4 text-muted-foreground">${p.cost_price.toFixed(2)}</td>
                            <td className="px-5 py-4 font-semibold text-emerald-400">{margin}%</td>
                            <td className="px-5 py-4">
                              <span
                                className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                                  p.stock > 0
                                    ? "bg-emerald-500/10 text-emerald-400"
                                    : "bg-destructive/10 text-destructive"
                                }`}
                              >
                                {p.stock > 0 ? `${p.stock} in stock` : "Out of stock"}
                              </span>
                            </td>
                            <td className="px-5 py-4">
                              <button
                                onClick={() => handleToggleFeatured(p)}
                                className={`text-xs font-bold px-2 py-0.5 rounded transition-colors ${
                                  p.is_featured
                                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                    : "bg-secondary text-muted-foreground hover:text-foreground"
                                }`}
                              >
                                {p.is_featured ? "⭐ Featured" : "Standard"}
                              </button>
                            </td>
                            <td className="px-5 py-4 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={() => setAddKeysProduct(p)}
                                  className="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded text-xs font-bold transition-colors"
                                  title="Bulk add license keys / accounts"
                                >
                                  + Add Keys
                                </button>
                                <button
                                  onClick={() => handleDeleteProduct(p.id)}
                                  className="p-1 text-rose-400 hover:text-rose-300 text-xs font-bold"
                                  title="Delete product"
                                >
                                  ✕
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 4: ORDERS & SALES ────────────────────────────────────────── */}
        {activeTab === "orders" && (
          <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
              <div className="relative w-full sm:w-80">
                <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search buyer, item, order ID..."
                  value={orderSearch}
                  onChange={(e) => setOrderSearch(e.target.value)}
                  className="w-full bg-secondary/60 border border-border/80 rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                />
              </div>
              <p className="text-xs text-muted-foreground font-medium">
                {filteredOrders.length} completed purchases recorded
              </p>
            </div>

            <div className="glass-card rounded-2xl overflow-hidden border border-border/50">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-secondary/70 border-b border-border/60 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Order ID</th>
                      <th className="px-5 py-3 font-semibold">Item Name</th>
                      <th className="px-5 py-3 font-semibold">Buyer</th>
                      <th className="px-5 py-3 font-semibold">Price</th>
                      <th className="px-5 py-3 font-semibold">Profit</th>
                      <th className="px-5 py-3 font-semibold">Delivered Key / Content</th>
                      <th className="px-5 py-3 font-semibold text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {filteredOrders.map((o) => (
                      <tr key={o.id} className="hover:bg-accent/40 transition-colors">
                        <td className="px-5 py-4 font-mono text-xs text-primary font-bold">
                          #{o.unique_id}
                        </td>
                        <td className="px-5 py-4 font-semibold text-foreground">{o.item_name}</td>
                        <td className="px-5 py-4">
                          <span className="font-medium text-foreground">{o.buyer_email || o.buyer_id}</span>
                        </td>
                        <td className="px-5 py-4 font-bold text-foreground">${o.price.toFixed(2)}</td>
                        <td className="px-5 py-4 font-semibold text-emerald-400">+${o.profit.toFixed(2)}</td>
                        <td className="px-5 py-4">
                          <button
                            onClick={() => setSelectedSecret({ title: o.item_name, content: o.value })}
                            className="px-2.5 py-1 bg-secondary hover:bg-secondary/80 text-foreground rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border border-border/50"
                          >
                            <Eye className="w-3 h-3 text-primary" /> View Key / Account
                          </button>
                        </td>
                        <td className="px-5 py-4 text-xs text-muted-foreground text-right whitespace-nowrap">
                          {o.bought_datetime ? new Date(o.bought_datetime).toLocaleString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 5: PAYMENTS & TXID ────────────────────────────────────────── */}
        {activeTab === "payments" && (
          <div className="space-y-6 animate-in fade-in duration-300">
            {/* Filter toolbar */}
            <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
              <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
                <div className="relative w-full sm:w-72">
                  <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search TxID, User ID, provider..."
                    value={paymentSearch}
                    onChange={(e) => setPaymentSearch(e.target.value)}
                    className="w-full bg-secondary/60 border border-border/80 rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                </div>

                <select
                  value={paymentProviderFilter}
                  onChange={(e) => setPaymentProviderFilter(e.target.value)}
                  className="bg-secondary/60 border border-border/80 rounded-xl px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary"
                >
                  <option value="all">All Providers</option>
                  <option value="bybit_uid">Bybit UID</option>
                  <option value="binance_uid">Binance Pay</option>
                  <option value="onchain_trc20">TRC20 (USDT)</option>
                  <option value="onchain_bep20">BEP20 (USDT)</option>
                  <option value="cryptopay">CryptoPay</option>
                  <option value="stars">Telegram Stars</option>
                </select>
              </div>

              <p className="text-xs text-muted-foreground font-medium">
                {filteredPayments.length} transactions
              </p>
            </div>

            <div className="glass-card rounded-2xl overflow-hidden border border-border/50">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-secondary/70 border-b border-border/60 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Gateway / Provider</th>
                      <th className="px-5 py-3 font-semibold">Transfer ID / Tx Hash</th>
                      <th className="px-5 py-3 font-semibold">User ID</th>
                      <th className="px-5 py-3 font-semibold">Amount</th>
                      <th className="px-5 py-3 font-semibold">Status</th>
                      <th className="px-5 py-3 font-semibold text-right">Created Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {filteredPayments.map((p) => (
                      <tr key={p.id} className="hover:bg-accent/40 transition-colors">
                        <td className="px-5 py-4">
                          <span className="font-bold text-foreground uppercase tracking-wider text-xs px-2.5 py-1 rounded bg-secondary">
                            {p.provider}
                          </span>
                        </td>
                        <td className="px-5 py-4 font-mono text-xs">
                          <div className="flex items-center gap-2">
                            <span className="text-foreground max-w-[200px] truncate" title={p.external_id}>
                              {p.external_id}
                            </span>
                            <button
                              onClick={() => copyToClipboard(p.external_id, `pay_${p.id}`)}
                              className="text-muted-foreground hover:text-foreground transition-colors p-1"
                              title="Copy Tx ID"
                            >
                              {copiedId === `pay_${p.id}` ? (
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </td>
                        <td className="px-5 py-4 font-mono text-xs text-muted-foreground">{p.user_id}</td>
                        <td className="px-5 py-4 font-bold text-primary">
                          ${p.amount.toFixed(2)} <span className="text-xs text-muted-foreground font-normal">{p.currency}</span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                                p.status === "succeeded"
                                  ? "bg-emerald-500/15 text-emerald-400"
                                  : p.status === "pending"
                                  ? "bg-amber-500/15 text-amber-400"
                                  : "bg-destructive/15 text-destructive"
                              }`}
                            >
                              {p.status}
                            </span>
                            {p.status === "pending" && (
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleApprovePayment(p.id)}
                                  className="px-2 py-0.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded text-[11px] font-bold"
                                  title="Approve & credit user balance"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => handleRejectPayment(p.id)}
                                  className="px-2 py-0.5 bg-rose-500 hover:bg-rose-600 text-white rounded text-[11px] font-bold"
                                  title="Reject payment"
                                >
                                  Reject
                                </button>
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-xs text-muted-foreground text-right whitespace-nowrap">
                          {p.created_at ? new Date(p.created_at).toLocaleString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 6: AUDIT LOGS ────────────────────────────────────────────── */}
        {activeTab === "audit" && (
          <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
              <div className="relative w-full sm:w-80">
                <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search actions, details, user..."
                  value={auditSearch}
                  onChange={(e) => setAuditSearch(e.target.value)}
                  className="w-full bg-secondary/60 border border-border/80 rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                />
              </div>
              <p className="text-xs text-muted-foreground font-medium">
                {filteredAuditLogs.length} audit trail events
              </p>
            </div>

            <div className="glass-card rounded-2xl overflow-hidden border border-border/50">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-secondary/70 border-b border-border/60 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Timestamp</th>
                      <th className="px-5 py-3 font-semibold">Level</th>
                      <th className="px-5 py-3 font-semibold">Action</th>
                      <th className="px-5 py-3 font-semibold">Actor / User ID</th>
                      <th className="px-5 py-3 font-semibold">Resource</th>
                      <th className="px-5 py-3 font-semibold">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {filteredAuditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-accent/40 transition-colors">
                        <td className="px-5 py-3.5 text-xs text-muted-foreground whitespace-nowrap">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                        </td>
                        <td className="px-5 py-3.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                              log.level === "ERROR"
                                ? "bg-destructive/20 text-destructive"
                                : log.level === "WARN"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-blue-500/20 text-blue-400"
                            }`}
                          >
                            {log.level}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 font-bold font-mono text-xs text-foreground">
                          {log.action}
                        </td>
                        <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">
                          {log.user_id || "System"}
                        </td>
                        <td className="px-5 py-3.5 text-xs text-muted-foreground">
                          {log.resource_type ? `${log.resource_type}: ${log.resource_id || ""}` : "—"}
                        </td>
                        <td className="px-5 py-3.5 text-xs text-foreground/90 max-w-xs truncate" title={log.details || ""}>
                          {log.details || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 7: NEPAL QR MANAGER ─────────────────────────────────────── */}
        {activeTab === "nepal_qr" && (
          <div className="space-y-8 animate-in fade-in duration-300">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-red-400 px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/20 inline-block mb-2">
                🇳🇵 Payment Configuration
              </span>
              <h2 className="text-3xl font-extrabold">Nepal QR Code Manager</h2>
              <p className="text-muted-foreground text-xs mt-1">
                Upload or update your eSewa, Khalti, or Fonepay QR image and payment instructions for Nepal customers.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Config Form */}
              <form onSubmit={handleSaveNepalQr} className="glass-card p-6 md:p-8 rounded-3xl space-y-5 border border-red-500/30">
                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1.5">
                    QR Code Image URL / File Link:
                  </label>
                  <input
                    type="text"
                    placeholder="https://i.imgur.com/your-qr-image.png or URL"
                    value={nepalQrUrl}
                    onChange={(e) => setNepalQrUrl(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-4 py-2.5 text-xs font-mono text-foreground focus:outline-none focus:border-red-500"
                  />
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Paste image URL (Imgur / Discord / Direct web link).
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1.5">
                    Payment Method Title:
                  </label>
                  <input
                    type="text"
                    placeholder="eSewa / Khalti / Fonepay Direct QR"
                    value={nepalQrTitle}
                    onChange={(e) => setNepalQrTitle(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-4 py-2.5 text-xs font-bold text-foreground focus:outline-none focus:border-red-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1.5">
                    Account Holder Name:
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Kali Store Nepal"
                    value={nepalQrAccountName}
                    onChange={(e) => setNepalQrAccountName(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-4 py-2.5 text-xs font-bold text-foreground focus:outline-none focus:border-red-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1.5">
                    eSewa / Fonepay Mobile Number / ID:
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. 9812345678"
                    value={nepalQrAccountId}
                    onChange={(e) => setNepalQrAccountId(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-4 py-2.5 text-xs font-mono font-bold text-foreground focus:outline-none focus:border-red-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1.5">
                    Customer Payment Instructions:
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Instructions for customers..."
                    value={nepalQrInstructions}
                    onChange={(e) => setNepalQrInstructions(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl p-3 text-xs text-foreground focus:outline-none focus:border-red-500"
                  />
                </div>

                <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-extrabold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                        <span>🇳🇵</span> Nepal Store "Coming Soon" Banner
                      </h4>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Enable to show a prominent "Coming Soon" message on the Nepal Store page, or turn off to remove it.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setNepalComingSoon(!nepalComingSoon)}
                      className={`px-3 py-1.5 rounded-xl font-black text-xs transition-all shadow-md flex items-center gap-1.5 ${
                        nepalComingSoon
                          ? 'bg-amber-500 text-black shadow-amber-500/30'
                          : 'bg-secondary text-muted-foreground border border-border'
                      }`}
                    >
                      {nepalComingSoon ? '✓ Banner Active' : '✕ Banner Hidden'}
                    </button>
                  </div>

                  {nepalComingSoon && (
                    <div className="pt-2 border-t border-amber-500/20">
                      <label className="block text-[11px] font-bold text-amber-300 uppercase mb-1">
                        Announcement Text:
                      </label>
                      <input
                        type="text"
                        value={nepalComingSoonText}
                        onChange={(e) => setNepalComingSoonText(e.target.value)}
                        className="w-full bg-black/40 border border-amber-500/30 rounded-xl px-3 py-2 text-xs text-foreground focus:outline-none focus:border-amber-400 font-medium"
                        placeholder="Coming soon announcement text..."
                      />
                    </div>
                  )}
                </div>

                {nepalQrSaveSuccess && (
                  <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 font-bold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>Nepal QR payment and Coming Soon settings saved successfully!</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSavingNepalQr}
                  className="w-full py-3 bg-red-500 hover:bg-red-600 text-white font-extrabold text-xs rounded-xl transition-all shadow-lg shadow-red-500/20 flex items-center justify-center gap-2"
                >
                  {isSavingNepalQr ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" /> Saving Configuration...
                    </>
                  ) : (
                    <>Save QR Payment Settings</>
                  )}
                </button>
              </form>

              {/* Live Preview Box */}
              <div className="glass-card p-6 md:p-8 rounded-3xl border border-border/60 flex flex-col items-center justify-center text-center">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-4">
                  Customer Checkout Preview
                </span>

                <div className="w-full max-w-sm p-5 rounded-2xl bg-black/40 border border-red-500/30 text-center space-y-3">
                  <span className="text-[11px] font-extrabold uppercase px-2.5 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 inline-block">
                    {nepalQrTitle || "eSewa / Fonepay Direct QR"}
                  </span>

                  {nepalQrUrl ? (
                    <div className="my-2 p-2 bg-white rounded-xl inline-block shadow-md">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={nepalQrUrl}
                        alt="Nepal Payment QR Code"
                        className="w-44 h-44 object-contain mx-auto"
                      />
                    </div>
                  ) : (
                    <div className="w-44 h-44 bg-secondary/80 rounded-xl border border-dashed border-border flex flex-col items-center justify-center mx-auto my-2 text-muted-foreground">
                      <Sparkles className="w-8 h-8 mb-1 text-red-400" />
                      <span className="text-[11px] font-bold">No Image Uploaded</span>
                    </div>
                  )}

                  <p className="text-xs font-bold text-foreground">
                    Account: <span className="text-primary">{nepalQrAccountName || "Kali Store Nepal"}</span>
                  </p>
                  <p className="text-xs font-mono text-muted-foreground">
                    ID / Number: <code>{nepalQrAccountId || "9800000000"}</code>
                  </p>
                  <p className="text-[11px] text-muted-foreground italic">
                    {nepalQrInstructions || "Scan QR code to pay exact NPR amount"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB: PROMOCODES & DISCOUNTS ──────────────────────────────────── */}
        {activeTab === "promocodes" && (
          <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
              <div>
                <h3 className="text-xl font-bold">Promocodes & Discount Coupons</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Manage store promo codes, percentage discounts, and max usage limits.</p>
              </div>
              <button
                onClick={() => setIsAddPromoOpen(true)}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all"
              >
                + Create Promocode
              </button>
            </div>

            <div className="glass-card rounded-2xl overflow-hidden border border-border/50">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-secondary/70 border-b border-border/60 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Code</th>
                      <th className="px-5 py-3 font-semibold">Discount</th>
                      <th className="px-5 py-3 font-semibold">Usage</th>
                      <th className="px-5 py-3 font-semibold">Status</th>
                      <th className="px-5 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {promocodes.map((promo) => (
                      <tr key={promo.id} className="hover:bg-accent/40 transition-colors">
                        <td className="px-5 py-4 font-mono font-bold text-foreground">{promo.code}</td>
                        <td className="px-5 py-4 font-bold text-emerald-400">
                          {promo.discount_type === "percent" ? `${promo.discount_value}% OFF` : `$${promo.discount_value} OFF`}
                        </td>
                        <td className="px-5 py-4 text-xs text-muted-foreground">
                          {promo.current_uses} / {promo.max_uses > 0 ? promo.max_uses : "∞"}
                        </td>
                        <td className="px-5 py-4">
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400">
                            {promo.is_active ? "Active" : "Disabled"}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <button
                            onClick={() => handleDeletePromo(promo.id)}
                            className="p-1 text-rose-400 hover:text-rose-300 text-xs font-bold"
                            title="Delete promocode"
                          >
                            ✕ Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── MODAL: CREATE PRODUCT ────────────────────────────────────────── */}
        {isAddProductOpen && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="glass-card p-6 md:p-8 rounded-2xl max-w-lg w-full border border-border shadow-2xl space-y-4">
              <h3 className="text-xl font-bold">Add New Digital Product</h3>
              <form onSubmit={handleCreateProduct} className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Product Name:</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. ChatGPT Plus Account"
                    value={newProdName}
                    onChange={(e) => setNewProdName(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:border-primary"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Category:</label>
                    <select
                      value={newProdCatId}
                      onChange={(e) => setNewProdCatId(parseInt(e.target.value))}
                      className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:border-primary"
                    >
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Warranty:</label>
                    <input
                      type="text"
                      placeholder="e.g. 24 Hours"
                      value={newProdWarranty}
                      onChange={(e) => setNewProdWarranty(e.target.value)}
                      className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-primary"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Sell Price ($ USD):</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      placeholder="e.g. 5.00"
                      value={newProdPrice}
                      onChange={(e) => setNewProdPrice(e.target.value)}
                      className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Cost Price ($ USD):</label>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="e.g. 2.50"
                      value={newProdCostPrice}
                      onChange={(e) => setNewProdCostPrice(e.target.value)}
                      className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-primary"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Initial Stock Keys / Accounts (One per line):</label>
                  <textarea
                    rows={4}
                    placeholder="user1:pass1&#10;user2:pass2&#10;KEY-12345"
                    value={newProdKeys}
                    onChange={(e) => setNewProdKeys(e.target.value)}
                    className="w-full bg-black/40 border border-border rounded-xl p-3 font-mono text-xs focus:outline-none focus:border-primary"
                  />
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddProductOpen(false)}
                    className="flex-1 py-2 bg-secondary text-secondary-foreground rounded-xl text-xs font-bold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold shadow-lg shadow-primary/20"
                  >
                    Create Product
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── MODAL: BULK ADD KEYS ────────────────────────────────────────── */}
        {addKeysProduct && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="glass-card p-6 rounded-2xl max-w-md w-full border border-border space-y-4">
              <h3 className="text-xl font-bold">Add Keys to {addKeysProduct.name}</h3>
              <form onSubmit={handleAddStockKeys} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Paste Stock Accounts / Keys (One per line):</label>
                  <textarea
                    rows={6}
                    required
                    placeholder="user1:pass1&#10;user2:pass2&#10;KEY-99999"
                    value={stockKeysInput}
                    onChange={(e) => setStockKeysInput(e.target.value)}
                    className="w-full bg-black/40 border border-border rounded-xl p-3 font-mono text-xs focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setAddKeysProduct(null)}
                    className="flex-1 py-2 bg-secondary rounded-xl text-xs font-bold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2 bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-500/20"
                  >
                    Add to Stock
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── MODAL: ADD CATEGORY ──────────────────────────────────────────── */}
        {isAddCategoryOpen && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="glass-card p-6 rounded-2xl max-w-sm w-full border border-border space-y-4">
              <h3 className="text-xl font-bold">Add New Category</h3>
              <form onSubmit={handleCreateCategory} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Category Name:</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Subscriptions"
                    value={newCategoryName}
                    onChange={(e) => setNewCategoryName(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:border-primary"
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setIsAddCategoryOpen(false)}
                    className="flex-1 py-2 bg-secondary rounded-xl text-xs font-bold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold"
                  >
                    Create
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── MODAL: CREATE PROMOCODE ──────────────────────────────────────── */}
        {isAddPromoOpen && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="glass-card p-6 rounded-2xl max-w-sm w-full border border-border space-y-4">
              <h3 className="text-xl font-bold">Create Promocode</h3>
              <form onSubmit={handleCreatePromo} className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Promo Code:</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. NEPAL50"
                    value={newPromoCode}
                    onChange={(e) => setNewPromoCode(e.target.value.toUpperCase())}
                    className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs font-mono font-bold uppercase focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Type:</label>
                    <select
                      value={newPromoType}
                      onChange={(e) => setNewPromoType(e.target.value)}
                      className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs font-bold focus:outline-none"
                    >
                      <option value="percent">Percentage (%)</option>
                      <option value="fixed">Fixed ($ USD)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Value:</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      placeholder="e.g. 20"
                      value={newPromoValue}
                      onChange={(e) => setNewPromoValue(e.target.value)}
                      className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs font-bold focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Max Uses (0 = Infinite):</label>
                  <input
                    type="number"
                    value={newPromoMaxUses}
                    onChange={(e) => setNewPromoMaxUses(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-3 py-2 text-xs focus:outline-none"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddPromoOpen(false)}
                    className="flex-1 py-2 bg-secondary rounded-xl text-xs font-bold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2 bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-500/20"
                  >
                    Create Code
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── MODAL: BALANCE ADJUST ────────────────────────────────────────── */}
        {balanceModalUser && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="glass-card p-6 md:p-8 rounded-2xl max-w-md w-full border border-border shadow-2xl space-y-6">
              <div>
                <h3 className="text-xl font-bold">Adjust User Balance</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  User: <span className="font-semibold text-foreground">{balanceModalUser.email || balanceModalUser.telegram_id}</span>
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Current Balance: <span className="font-bold text-primary">${balanceModalUser.balance.toFixed(2)}</span>
                </p>
              </div>

              <form onSubmit={handleBalanceSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase text-muted-foreground mb-1.5">
                    Amount to Add (+) or Deduct (-) (USD)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="e.g. 50.00 or -20.00"
                    value={balanceAdjustAmount}
                    onChange={(e) => setBalanceAdjustAmount(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-primary"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase text-muted-foreground mb-1.5">
                    Reason / Audit Note
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Compensation, Promo grant, manual correction"
                    value={balanceAdjustReason}
                    onChange={(e) => setBalanceAdjustReason(e.target.value)}
                    className="w-full bg-secondary border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-primary"
                  />
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setBalanceModalUser(null)}
                    className="flex-1 py-2.5 bg-secondary hover:bg-secondary/80 text-secondary-foreground rounded-xl text-sm font-semibold transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2.5 bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl text-sm font-bold shadow-lg shadow-primary/20 transition-all"
                  >
                    Confirm Adjust
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── MODAL: VIEW DELIVERED CONTENT / KEY ──────────────────────────── */}
        {selectedSecret && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="glass-card p-6 md:p-8 rounded-2xl max-w-lg w-full border border-border shadow-2xl space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-bold">{selectedSecret.title}</h3>
                <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary font-bold">
                  Delivered Asset
                </span>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-muted-foreground mb-2">
                  Content / Account Credentials / Serial Key:
                </label>
                <div className="relative">
                  <textarea
                    readOnly
                    value={selectedSecret.content}
                    rows={6}
                    className="w-full bg-black/50 border border-border rounded-xl p-4 font-mono text-xs text-foreground focus:outline-none resize-none select-all"
                  />
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => copyToClipboard(selectedSecret.content, "secret_modal")}
                  className="flex-1 py-2.5 bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2"
                >
                  {copiedId === "secret_modal" ? (
                    <>
                      <Check className="w-4 h-4" /> Copied to Clipboard!
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" /> Copy Content
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedSecret(null)}
                  className="px-5 py-2.5 bg-secondary hover:bg-secondary/80 text-secondary-foreground rounded-xl text-sm font-semibold transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
