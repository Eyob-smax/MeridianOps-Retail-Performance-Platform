import { createRouter, createWebHistory } from "vue-router";

import RoleShell from "@/components/layout/RoleShell.vue";
import { useAuthStore } from "@/stores/auth";
import type { UserRole } from "@/types/roles";
import LoginView from "@/views/auth/LoginView.vue";
import AdminSecurityView from "@/views/app/AdminSecurityView.vue";
import AnalyticsBuilderView from "@/views/app/AnalyticsBuilderView.vue";
import AnalyticsView from "@/views/app/AnalyticsView.vue";
import AttendanceRequestsView from "@/views/app/AttendanceRequestsView.vue";
import AttendanceView from "@/views/app/AttendanceView.vue";
import CampaignDetailView from "@/views/app/CampaignDetailView.vue";
import CampaignNewView from "@/views/app/CampaignNewView.vue";
import CampaignsView from "@/views/app/CampaignsView.vue";
import CheckoutView from "@/views/app/CheckoutView.vue";
import HomeView from "@/views/app/HomeView.vue";
import InventoryCountsView from "@/views/app/InventoryCountsView.vue";
import InventoryReceivingView from "@/views/app/InventoryReceivingView.vue";
import InventoryTransfersView from "@/views/app/InventoryTransfersView.vue";
import MembersView from "@/views/app/MembersView.vue";
import SharedDashboardView from "@/views/shared/SharedDashboardView.vue";
import TrainingReviewView from "@/views/app/TrainingReviewView.vue";
import TrainingView from "@/views/app/TrainingView.vue";
import HealthView from "@/views/system/HealthView.vue";

const allRoles: UserRole[] = [
  "administrator",
  "store_manager",
  "inventory_clerk",
  "cashier",
  "employee",
];

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/login" },
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { requiresGuest: true },
    },
    {
      path: "/shared/:token",
      name: "shared-dashboard",
      component: SharedDashboardView,
    },
    {
      path: "/app",
      component: RoleShell,
      meta: { requiresAuth: true },
      children: [
        { path: "home", component: HomeView, meta: { roles: allRoles } },
        {
          path: "campaigns",
          component: CampaignsView,
          meta: { roles: ["administrator", "store_manager"] },
        },
        {
          path: "campaigns/new",
          component: CampaignNewView,
          meta: { roles: ["administrator", "store_manager"] },
        },
        {
          path: "campaigns/:id",
          component: CampaignDetailView,
          meta: { roles: ["administrator", "store_manager", "cashier"] },
        },
        {
          path: "checkout",
          component: CheckoutView,
          meta: { roles: ["administrator", "store_manager", "cashier"] },
        },
        {
          path: "members",
          component: MembersView,
          meta: { roles: ["administrator", "store_manager", "cashier"] },
        },
        {
          path: "training",
          component: TrainingView,
          meta: { roles: ["administrator", "store_manager", "employee"] },
        },
        {
          path: "training/review",
          component: TrainingReviewView,
          meta: { roles: ["administrator", "store_manager", "employee"] },
        },
        {
          path: "inventory/receiving",
          component: InventoryReceivingView,
          meta: { roles: ["administrator", "store_manager", "inventory_clerk"] },
        },
        {
          path: "inventory/transfers",
          component: InventoryTransfersView,
          meta: { roles: ["administrator", "store_manager", "inventory_clerk"] },
        },
        {
          path: "inventory/counts",
          component: InventoryCountsView,
          meta: { roles: ["administrator", "store_manager", "inventory_clerk"] },
        },
        {
          path: "attendance/check",
          component: AttendanceView,
          meta: { roles: ["administrator", "store_manager", "employee"] },
        },
        {
          path: "attendance/requests",
          component: AttendanceRequestsView,
          meta: { roles: ["administrator", "store_manager", "employee"] },
        },
        {
          path: "analytics",
          component: AnalyticsView,
          meta: { roles: ["administrator", "store_manager"] },
        },
        {
          path: "analytics/builder",
          component: AnalyticsBuilderView,
          meta: { roles: ["administrator", "store_manager"] },
        },
        {
          path: "admin/security",
          component: AdminSecurityView,
          meta: { roles: ["administrator"] },
        },
        { path: "system/health", component: HealthView, meta: { roles: allRoles } },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  await auth.initialize();

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return "/login";
  }

  if (to.meta.requiresGuest && auth.isAuthenticated) {
    return "/app/home";
  }

  if (auth.isAuthenticated) {
    const allowedRoles = to.matched
      .flatMap((record) => (record.meta.roles as UserRole[] | undefined) ?? [])
      .filter((value, index, arr) => arr.indexOf(value) === index);

    if (allowedRoles.length > 0) {
      const hasAccess = auth.roles.some((role) => allowedRoles.includes(role));
      if (!hasAccess) {
        return "/app/home";
      }
    }
  }

  return true;
});

export default router;
