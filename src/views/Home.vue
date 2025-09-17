<template>
  <div style="width: 100%; min-height: 100vh; background: white; display: flex; justify-content: center; align-items: center; padding-top: 95px; position: relative;">
    <div style="position: relative; width: 1600px; height: 900px; display: flex; justify-content: center; align-items: center;">
      
      <!-- Center orange gradient circle -->
      <div style="
        position: absolute;
        width: 900px;
        height: 900px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255, 97, 44, 0.4) 0%, white 100%);
        box-shadow: 0 0 80px rgba(255, 97, 44, 0.2);
      "></div>

      <!-- Welcome + text blocks -->
      <div style="position: relative; z-index: 1; text-align: center;">
        <h1 style="
          font-size: 64px;
          font-weight: 700;
          color: #FF612C;
          margin-bottom: 40px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen-Sans, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
        ">
          Welcome Back!
        </h1>

        <!-- Left-right structure -->
        <div style="display: flex; flex-direction: row; justify-content: center; align-items: flex-start; gap: 120px; font-size: 24px;">
          <div style="text-align: left; color: #333; font-weight: 600; line-height: 2;">
            <div v-if="hasPermission('Parameter')">› Upload Data</div>
            <div v-if="hasPermission('Run Management')">› Run ECL</div>
            <div v-if="hasPermission('Role Management')">› Role Management</div>
            <div v-if="hasPermission('Audit Trial')">› Audit Trial</div>
            <div v-if="hasPermission('Reporting')">› Reporting</div>
          </div>

          <!-- Right side links - only show pages user has permission for -->
          <div style="text-align: left; font-weight: 600; line-height: 2;">
            <router-link v-if="hasPermission('Parameter')" to="/parameter" style="color: #FF612C; text-decoration: underline;">Parameter</router-link><br v-if="hasPermission('Parameter')">
            <router-link v-if="hasPermission('Run Management')" to="/run-management" style="color: #FF612C; text-decoration: underline;">Run Management</router-link><br v-if="hasPermission('Run Management')">
            <router-link v-if="hasPermission('Role Management')" to="/role-management" style="color: #FF612C; text-decoration: underline;">Role Management</router-link><br v-if="hasPermission('Role Management')">
            <router-link v-if="hasPermission('Audit Trial')" to="/audit-trial" style="color: #FF612C; text-decoration: underline;">AuditTrial</router-link><br v-if="hasPermission('Audit Trial')">
            <router-link v-if="hasPermission('Reporting')" to="/reporting" style="color: #FF612C; text-decoration: underline;">Reporting</router-link><br v-if="hasPermission('Reporting')">
          </div>

        </div>

        <!-- If no permissions, show message -->
        <div v-if="!hasAnyPermission(['Parameter', 'Run Management', 'Role Management', 'Audit Trial', 'Reporting'])" style="margin-top: 40px; color: #666; font-size: 18px;">
          <p>You don't have access to any functions at the moment.</p>
          <p>Please contact your administrator to get proper permissions.</p>
        </div>
      </div>
    </div>

    <!-- Page bottom right version number -->
    <div style="
      position: fixed;
      right: 20px;
      bottom: 10px;
      font-size: 20px;
      color: #999;
      z-index: 1000;
    ">
      Version: Python 3.10
    </div>
  </div>
</template>

<script setup lang="ts">
import { hasPermission, hasAnyPermission } from '../services/authService'
</script>