import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Parameter from '../views/Parameter.vue'
import RunManagement from '../views/RunManagement.vue'
import RoleManagement from '../views/RoleManagement.vue'
import AuditTrial from '../views/AuditTrial.vue'
import Reporting from '../views/Reporting.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/parameter',
    name: 'Parameter',
    component: Parameter
  },
  {
    path: '/run-management',
    name: 'RunManagement',
    component: RunManagement
  },
  {
    path: '/role-management',
    name: 'RoleManagement',
    component: RoleManagement
  },
  {
    path: '/audit-trial',
    name: 'AuditTrial',
    component: AuditTrial
  },
  {
    path: '/reporting',
    name: 'Reporting',
    component: Reporting
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
