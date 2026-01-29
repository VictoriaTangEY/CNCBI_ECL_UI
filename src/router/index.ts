import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Parameter from '../views/Parameter.vue'
import RunManagement from '../views/RunManagement.vue'
import RoleManagement from '../views/RoleManagement.vue'
import AuditTrial from '../views/AuditTrial.vue'
import Reporting from '../views/Reporting.vue'
import Login from '../views/Login.vue'
import { isAuthenticated, waitForAuthInit } from '../services/authService'
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
router.beforeEach(async (to, _from, next) => {
  await waitForAuthInit()
  
  const requiresAuth = to.meta.requiresAuth !== false
  const userAuthenticated = isAuthenticated()
  
  if (requiresAuth && !userAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && userAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router