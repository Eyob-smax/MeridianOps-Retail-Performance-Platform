import type { UserRole } from "@/types/roles";

export interface NavigationItem {
  name: string;
  path: string;
  roles: UserRole[];
}

export const navigationItems: NavigationItem[] = [
  {
    name: "Home",
    path: "/app/home",
    roles: ["administrator", "store_manager", "inventory_clerk", "cashier", "employee"],
  },
  { name: "Campaigns", path: "/app/campaigns", roles: ["administrator", "store_manager"] },
  { name: "Checkout", path: "/app/checkout", roles: ["administrator", "store_manager", "cashier"] },
  { name: "Members", path: "/app/members", roles: ["administrator", "store_manager", "cashier"] },
  {
    name: "Training",
    path: "/app/training",
    roles: ["administrator", "store_manager", "employee"],
  },
  {
    name: "Inventory Receiving",
    path: "/app/inventory/receiving",
    roles: ["administrator", "store_manager", "inventory_clerk"],
  },
  {
    name: "Inventory Transfers",
    path: "/app/inventory/transfers",
    roles: ["administrator", "store_manager", "inventory_clerk"],
  },
  {
    name: "Inventory Counts",
    path: "/app/inventory/counts",
    roles: ["administrator", "store_manager", "inventory_clerk"],
  },
  {
    name: "Attendance Check",
    path: "/app/attendance/check",
    roles: ["administrator", "store_manager", "employee"],
  },
  {
    name: "Attendance Requests",
    path: "/app/attendance/requests",
    roles: ["administrator", "store_manager", "employee"],
  },
  { name: "Analytics", path: "/app/analytics", roles: ["administrator", "store_manager"] },
  {
    name: "Analytics Builder",
    path: "/app/analytics/builder",
    roles: ["administrator", "store_manager"],
  },
  { name: "Security", path: "/app/admin/security", roles: ["administrator"] },
  {
    name: "Health",
    path: "/app/system/health",
    roles: ["administrator", "store_manager", "inventory_clerk", "cashier", "employee"],
  },
];
