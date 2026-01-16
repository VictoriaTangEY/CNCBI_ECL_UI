import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Parameter from '../views/Parameter.vue'
import RunManagement from '../views/RunManagement.vue'
import RoleManagement from '../views/RoleManagement.vue'
import AuditTrial from '../views/AuditTrial.vue'
import Reporting from '../views/Reporting.vue'
import Login from '../views/Login.vue'
import { isAuthenticated } from '../services/authService'
 
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true }
  },
  {
    path: '/parameter',
    name: 'Parameter',
    component: Parameter,
    meta: { requiresAuth: true }
  },
  {
    path: '/run-management',
    name: 'RunManagement',
    component: RunManagement,
    meta: { requiresAuth: true }
  },
  {
    path: '/role-management',
    name: 'RoleManagement',
    component: RoleManagement,
    meta: { requiresAuth: true }
  },
  {
    path: '/audit-trial',
    name: 'AuditTrial',
    component: AuditTrial,
    meta: { requiresAuth: true }
  },
  {
    path: '/reporting',
    name: 'Reporting',
    component: Reporting,
    meta: { requiresAuth: true }
  }
]
 
const router = createRouter({
  history: createWebHistory('/ecl/'),
  routes
})

// Navigation Guards
router.beforeEach((to, _from, next) => {
  const requiresAuth = to.meta.requiresAuth !== false
  const userAuthenticated = isAuthenticated()

  if (requiresAuth && !userAuthenticated) {
    // Redirect to login if authentication is required but user is not authenticated
    next('/login')
  } else if (to.path === '/login' && userAuthenticated) {
    // Redirect to home if user is already authenticated and trying to access login
    next('/')
  } else {
    // Allow navigation
    next()
  }
})

export default router