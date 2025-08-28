<template>
  <div>
    <!-- Loading State - Show during authentication check -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-container">
        <h2>Loading...</h2>
        <p>Please wait...</p>
      </div>
    </div>

    <!-- Main Application (shown for authenticated users) -->
    <div v-else-if="isAuthenticated()">
      <!-- Navigation Bar -->
      <div class="navbar">
        <!-- Logo -->
        <div class="logo">
          <img alt="Group" src="/group.png" />
          <img alt="Vector" src="/vector.svg" />
        </div>
        
        <!-- Navigation Links (only show permitted functions) -->
        <div class="nav-links">
          <router-link v-if="hasPermission('Home')" to="/">Home</router-link>
          <router-link v-if="hasPermission('Parameter')" to="/parameter">Parameter</router-link>
          <router-link v-if="hasPermission('Run Management')" to="/run-management">Run Management</router-link>
          <router-link v-if="hasPermission('Reporting')" to="/reporting">Reporting</router-link>
          <router-link v-if="hasPermission('Role Management')" to="/role-management">Role Management</router-link>
          <router-link v-if="hasPermission('Audit Trial')" to="/audit-trial">Audit Trial</router-link>
        </div>

        <!-- User Authentication Status -->
        <div class="user-info">
          <div class="authenticated-user">
            <span class="user-name">{{ getUserDisplayName() }}</span>
            <span class="user-role">{{ getUserRole() }}</span>
            <button @click="handleLogout" class="logout-button">
              <svg class="logout-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke-width="2"/>
                <polyline points="16,17 21,12 16,7" stroke-width="2"/>
                <line x1="21" y1="12" x2="9" y2="12" stroke-width="2"/>
              </svg>
              Logout
            </button>
          </div>
        </div>
      </div>

      <!-- Router View for authenticated users -->
      <router-view></router-view>
    </div>

    <!-- Login/Unauthenticated State - Show router-view for login page -->
    <div v-else>
      <router-view></router-view>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { 
  isAuthenticated, 
  hasPermission, 
  getUserDisplayName, 
  getUserRole, 
  logout,
  loading,
  initializeAuth
} from './services/authService'

const router = useRouter()

// Handle logout
async function handleLogout() {
  await logout()
  router.push('/login')
}

// Initialize authentication when component mounts
onMounted(async () => {
  console.log('App component mounted, initializing authentication...')
  await initializeAuth()
})
</script>

<style scoped>
.navbar {
  position: fixed;
  top: 0;
  width: 100%;
  background: white;
  z-index: 1000;
  height: 95px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  margin-left: 27px;
}

.logo img:first-child {
  width: 42px;
  height: 41px;
  margin-right: 7px;
}

.logo img:last-child {
  width: 198px;
  height: 41px;
}

.nav-links {
  display: flex;
  gap: 30px;
  margin-left: 50px;
}

.nav-links a,
.nav-links router-link {
  text-decoration: none;
  color: #333;
  font-weight: 500;
  font-size: 18px;
  padding: 8px 4px;
  transition: color 0.3s;
}

.nav-links a:hover,
.nav-links router-link:hover {
  color: #ff612c;
}

.router-link-active {
  color: #ff612c !important;
  border-bottom: 2px solid #ff612c;
}

.user-info {
  display: flex;
  align-items: center;
  margin-right: 30px;
  padding: 10px 15px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.authenticated-user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.user-name {
  font-weight: 600;
  color: #153D77;
  font-size: 14px;
}

.user-role {
  font-size: 12px;
  color: #6c757d;
}

.logout-button {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #dc3545;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.logout-button:hover {
  background: #c82333;
}

.logout-icon {
  width: 14px;
  height: 14px;
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #fff3cd;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-container {
  background: white;
  padding: 40px;
  border-radius: 10px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  max-width: 400px;
}

.loading-container h2 {
  color: #856404;
  margin-bottom: 20px;
}

.loading-container p {
  color: #856404;
  font-size: 16px;
}
</style>