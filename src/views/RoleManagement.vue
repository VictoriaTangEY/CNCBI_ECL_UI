<template>
  <div style="display: flex; min-height: 100vh; margin-top: 95px;">
    <!-- 左侧导航菜单 -->
    <aside style="width: 280px; background-color: #f5f5f5; padding: 30px 20px;">
      <h3 style="font-weight: bold; font-size: 22px; margin-bottom: 24px;">Role Management</h3>
      <ul style="list-style: none; padding-left: 0;">
        <li @click="currentTab = 'maintenance'" :style="{ cursor: 'pointer', color: currentTab === 'maintenance' ? '#ff612c' : '#333', fontWeight: currentTab === 'maintenance' ? '600' : 'normal', marginBottom: '10px', fontSize: '20px' }">▸ Role Maintenance</li>
        <li @click="currentTab = 'function'" :style="{ cursor: 'pointer', color: currentTab === 'function' ? '#ff612c' : '#333', fontWeight: currentTab === 'function' ? '600' : 'normal', marginBottom: '10px', fontSize: '20px' }">▸ Function Maintenance</li>
        <li @click="currentTab = 'assignment'" :style="{ cursor: 'pointer', color: currentTab === 'assignment' ? '#ff612c' : '#333', fontWeight: currentTab === 'assignment' ? '600' : 'normal', fontSize: '20px' }">▸ Role-Function Maintenance</li>
      </ul>
    </aside>

    <!-- 主要内容区域 -->
    <main style="flex-grow: 1; padding: 40px;">

      <!-- 面包屑导航 -->
      <nav aria-label="breadcrumb" class="breadcrumb-nav">
        <ol class="breadcrumb-list">
          <li><svg style="width:16px; height:16px; fill:#666; vertical-align:middle;" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg> Home</li>
          <li>Role Management</li>
          <li>{{ currentTab === 'maintenance' ? 'Role Maintenance' : currentTab === 'function' ? 'Function Maintenance' : 'Role-Function Maintenance' }}</li>
        </ol>
      </nav>

      <!-- Configuration Box with Progress Bar -->
      <div class="config-outer-box" v-if="currentTab === 'maintenance'">
        <div class="config-inner-box">
          <h2 class="upload-title">Role Maintenance</h2>
          <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e0e0e0;">
            <thead style="background: #f7f7f7;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Role Name</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Last Updated</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Last Updated By</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(role, index) in roles" :key="index">
                <td style="padding: 12px; text-align: center; color: #007bff; cursor: pointer;">{{ role.roleName }}</td>
                <td :style="{ padding: '12px', textAlign: 'center', color: role.status === 'Active' ? '#4CAF50' : '#f44336' }">
                  {{ role.status === 'Inactive' ? 'D' : role.status }}
                </td>
                <td style="padding: 12px; text-align: center;">{{ formatDate(role.lastUpdated) }}</td>
                <td style="padding: 12px; text-align: center;">{{ role.lastUpdatedBy }}</td>
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="openRoleModal(true, role)">Edit</button>
                  </div>
                </td>
              </tr>
              <tr v-if="showAddRow">
                <td style="padding: 12px; text-align: center;"><input v-model="newRole.roleName" placeholder="Role Name" class="select-input-full" style="text-align: center;" /></td>
                <td style="padding: 12px; text-align: center;">
                  <select v-model="newRole.status" class="select-input-full" style="text-align: center;">
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </td>
                <td style="padding: 12px; text-align: center;">-</td>
                <td style="padding: 12px; text-align: center;">-</td>
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="saveNewRole">Save</button>
                    <button class="step-btn" @click="cancelAddRow">Cancel</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div style="margin-top: 15px; text-align: right;" v-if="currentTab === 'maintenance'">
        <button class="upload-button" @click="addNewRoleRow">Add New Role</button>
      </div>
      <!-- Function Maintenance Table -->
      <div class="config-outer-box" v-if="currentTab === 'function'">
        <div class="config-inner-box">
          <h2 class="upload-title">Function Maintenance</h2>
          <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e0e0e0;">
            <thead style="background: #f7f7f7;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Function Name</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Last Updated</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Last Updated By</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(func, idx) in allFunctions" :key="idx">
                <td style="padding: 12px; text-align: center; color: #007bff; cursor: pointer;">{{ func.name }}</td>
                <td :style="{ padding: '12px', textAlign: 'center', color: func.status === 'Active' ? '#4CAF50' : '#f44336' }">
                  {{ func.status === 'Inactive' ? 'D' : func.status }}
                </td>
                <td style="padding: 12px; text-align: center;">{{ formatDate(func.lastUpdated) }}</td>
                <td style="padding: 12px; text-align: center;">{{ func.lastUpdatedBy }}</td>
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="openEditFunctionModalFunc(idx)">Edit</button>
                  </div>
                </td>
              </tr>
              <tr v-if="showAddFunctionRow">
                <td style="padding: 12px; text-align: center;"><input v-model="newFunction.name" placeholder="Function Name" class="select-input-full" style="text-align: center;" /></td>
                <td style="padding: 12px; text-align: center;">
                  <select v-model="newFunction.status" class="select-input-full" style="text-align: center;">
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </td>
                <td style="padding: 12px; text-align: center;">-</td>
                <td style="padding: 12px; text-align: center;">-</td>
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="saveNewFunction">Save</button>
                    <button class="step-btn" @click="cancelAddFunctionRow">Cancel</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div style="margin-top: 15px; text-align: right;" v-if="currentTab === 'function'">
        <button class="upload-button" @click="addNewFunctionRow">Add New Function</button>
      </div>
      <div class="config-outer-box" v-if="currentTab === 'assignment'">
        <div class="config-inner-box">
          <h2 class="upload-title">Role-Function Assignment</h2>
          <div style="margin-bottom: 20px;">
            <select v-model="selectedRole" class="select-input-full">
              <option value="" disabled>Select Role</option>
              <option v-for="role in activeRoles" :key="role" :value="role">{{ role }}</option>
            </select>
          </div>
          <div v-if="selectedRole">
            <h3 style="margin-bottom: 10px;">Assigned Functions for {{ selectedRole }}</h3>
            <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e0e0e0;">
              <thead style="background: #f7f7f7;">
                <tr>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Function</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Status</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Last Updated</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Last Updated By</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(func, idx) in allFunctions" :key="idx">
                  <td style="padding: 12px; text-align: center;">{{ func.name }}</td>
                  <td
                    :style="{
                      padding: '12px',
                      textAlign: 'center',
                      color: getFunctionStatusForRole(selectedRole, func.name) === 'Active' ? '#4CAF50' : '#f44336'
                    }"
                  >
                    {{ getFunctionStatusForRole(selectedRole, func.name) === 'Active' ? 'Active' : 'D' }}
                  </td>
                  <td style="padding: 12px; text-align: center;">{{ formatDate(func.lastUpdated) }}</td>
                  <td style="padding: 12px; text-align: center;">{{ func.lastUpdatedBy }}</td>
                  <td style="padding: 12px; text-align: center;">
                    <div style="display: flex; gap: 10px; justify-content: center;">
                      <button class="step-btn" @click="openEditFunctionModal(idx)">Edit</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <div style="margin-top: 15px; text-align: right;">
              <button class="upload-button" @click="saveRoleFunctionMappings">Save</button>
            </div>
          </div>
        </div>
      </div>
      <!-- Role Modal -->
      <div v-if="showRoleModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center;">
        <div style="background: white; padding: 20px; width: 400px; border-radius: 10px;">
          <h3>{{ isEditing ? 'Edit Role' : 'Add New Role' }}</h3>
          <div style="margin-top: 10px;">
            <input v-model="roleForm.roleName" placeholder="Role Name" class="select-input-full" />
            <select v-model="roleForm.status" class="select-input-full" style="margin-top: 10px;">
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>
          <div style="margin-top: 15px; text-align: right;">
            <button class="step-btn" @click="saveRole">Save</button>
            <button class="step-btn" @click="closeRoleModal">Cancel</button>
          </div>
        </div>
      </div>
      <!-- Add New Function Modal -->
      <div v-if="showAddFunctionModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000;">
        <div style="background: white; padding: 20px; width: 350px; border-radius: 10px;">
          <h3>Add New Function</h3>
          <input v-model="newFunctionName" placeholder="Function Name" class="select-input-full" style="margin-top: 10px;" />
          <div style="margin-top: 15px; text-align: right;">
            <button class="step-btn" @click="addFunction">Save</button>
            <button class="step-btn" @click="closeAddFunctionModal">Cancel</button>
          </div>
        </div>
      </div>
      <!-- Edit Function Modal for Function Maintenance -->
      <div v-if="showEditFunctionModal && currentTab === 'function'" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000;">
        <div style="background: white; padding: 20px; width: 350px; border-radius: 10px;">
          <h3>Edit Function</h3>
          <input v-model="editFunctionNameFunc" placeholder="Function Name" class="select-input-full" style="margin-top: 10px;" />
          <div style="margin-top: 15px;">
            <label>Status: </label>
            <select v-if="editFunctionIdxFunc !== null" v-model="allFunctions[editFunctionIdxFunc].status" class="select-input-full" style="width: 120px; display: inline-block;">
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>
          <div style="margin-top: 15px; text-align: right;">
            <button class="step-btn" @click="saveEditFunctionFunc">Save</button>
            <button class="step-btn" @click="closeEditFunctionModalFunc">Cancel</button>
          </div>
        </div>
      </div>
      <!-- Edit Function Modal for Role-Function Maintenance -->
      <div v-if="showEditFunctionModal && currentTab === 'assignment'" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000;">
        <div style="background: white; padding: 20px; width: 350px; border-radius: 10px;">
          <h3>Edit Function Mapping</h3>
          <input v-model="editFunctionName" placeholder="Function Name" class="select-input-full" style="margin-top: 10px;" disabled />
          <div style="margin-top: 15px;">
            <label>Status: </label>
            <select v-model="roleFunctionEditStatus" class="select-input-full" style="width: 120px; display: inline-block;">
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>
          <div style="margin-top: 15px; text-align: right;">
            <button class="step-btn" @click="saveEditFunctionMapping">Save</button>
            <button class="step-btn" @click="closeEditFunctionModal">Cancel</button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const currentTab = ref('maintenance')
const showRoleModal = ref(false)
const isEditing = ref(false)
const showAddRow = ref(false)
const newRole = ref({ roleName: '', roleId: '', status: 'Active' })
const roleForm = ref({ roleName: '', roleId: '', status: 'Active', remark: '' })
const originalRoleId = ref('')

const roles = ref([
  { roleName: 'Admin', roleId: 'R001', status: 'Active', lastUpdated: '2025-07-01 12:00', lastUpdatedBy: 'User1' },
  { roleName: 'RMG', roleId: 'R002', status: 'Active', lastUpdated: '2025-07-02 15:00', lastUpdatedBy: 'User2' },
])

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function getFunctionStatusForRole(roleName: string, functionName: string): string {
  return roleFunctionStatusMap.value[roleName]?.[functionName] || 'Inactive'
}

function openRoleModal(edit: boolean, role: any = null) {
  isEditing.value = edit
  if (edit && role) {
    roleForm.value = { ...role, remark: '' }
    originalRoleId.value = role.roleId
  } else {
    roleForm.value = { roleName: '', roleId: '', status: 'Active', remark: '' }
    originalRoleId.value = ''
  }
  showRoleModal.value = true
}

function closeRoleModal() {
  showRoleModal.value = false
}

function saveRole() {
  if (isEditing.value) {
    const idx = roles.value.findIndex(r => r.roleId === originalRoleId.value)
    if (idx > -1) {
      // If roleName changed, update activeRoles
      const oldName = roles.value[idx].roleName
      roles.value[idx] = { ...roleForm.value, lastUpdated: new Date().toISOString(), lastUpdatedBy: 'Admin' }
      if (oldName !== roleForm.value.roleName) {
        const i = activeRoles.value.indexOf(oldName)
        if (i > -1) activeRoles.value[i] = roleForm.value.roleName
        // 如果roleName变了，roleFunctions也要迁移
        if (roleFunctionStatusMap.value[oldName]) {
          roleFunctionStatusMap.value[roleForm.value.roleName] = roleFunctionStatusMap.value[oldName]
          delete roleFunctionStatusMap.value[oldName]
        } else {
          roleFunctionStatusMap.value[roleForm.value.roleName] = {}
        }
      }
    }
  } else {
    roles.value.push({ ...roleForm.value, lastUpdated: new Date().toISOString(), lastUpdatedBy: 'Admin' })
    if (!activeRoles.value.includes(roleForm.value.roleName)) {
      activeRoles.value.push(roleForm.value.roleName)
    }
    // 新增role时初始化function数组
    if (!roleFunctionStatusMap.value[roleForm.value.roleName]) {
      roleFunctionStatusMap.value[roleForm.value.roleName] = {}
    }
  }
  closeRoleModal()
}

function addNewRoleRow() {
  showAddRow.value = true
  newRole.value = { roleName: '', roleId: '', status: 'Active' }
}

function saveNewRole() {
  if (!newRole.value.roleName) return
  // Generate a roleId if not provided
  const roleId = newRole.value.roleId || `R${String(roles.value.length + 1).padStart(3, '0')}`
  roles.value.push({
    ...newRole.value,
    roleId: roleId,
    lastUpdated: new Date().toISOString(),
    lastUpdatedBy: 'Admin'
  })
  // Add to activeRoles for selection box
  if (!activeRoles.value.includes(newRole.value.roleName)) {
    activeRoles.value.push(newRole.value.roleName)
  }
  // 新增role时初始化function数组
  if (!roleFunctionStatusMap.value[newRole.value.roleName]) {
    roleFunctionStatusMap.value[newRole.value.roleName] = {}
  }
  showAddRow.value = false
}

function cancelAddRow() {
  showAddRow.value = false
}

const activeRoles = ref(['Admin', 'RMG'])
const selectedRole = ref('')

// 角色功能映射表 - 跟踪每个角色对应的功能状态
// 当前使用硬编码数据，后续将替换为SQL数据库
const roleFunctionStatusMap = ref<{ [role: string]: { [funcName: string]: string } }>({
  'Admin': {
    'Home': 'Active',
    'Parameter': 'Active', 
    'Run Management': 'Active',
    'Role Management': 'Active',
    'Audit Trial': 'Active'
  },
  'RMG': {
    'Home': 'Active',
    'Parameter': 'Active',
    'Run Management': 'Active', 
    'Role Management': 'Inactive',
    'Audit Trial': 'Active'
  }
});

// 编辑功能弹窗控制变量
const showEditFunctionModal = ref(false)
const showAddFunctionModal = ref(false)
const editFunctionName = ref('')
const editFunctionIdx = ref<number|null>(null)

function addFunction() {
  if (!selectedRole.value || !newFunctionName.value.trim()) return
  if (!roleFunctionStatusMap.value[selectedRole.value]) {
    roleFunctionStatusMap.value[selectedRole.value] = {}
  }
  roleFunctionStatusMap.value[selectedRole.value][newFunctionName.value.trim()] = 'Active'
  showAddFunctionModal.value = false
  newFunctionName.value = ''
}

function closeAddFunctionModal() {
  showAddFunctionModal.value = false
  newFunctionName.value = ''
}

// 编辑功能相关函数
function openEditFunctionModal(idx: number) {
  editFunctionIdx.value = idx
  editFunctionName.value = allFunctions.value[idx].name // 确保功能名称有值
  roleFunctionEditStatus.value = getFunctionStatusForRole(selectedRole.value, editFunctionName.value)
  showEditFunctionModal.value = true
}

function closeEditFunctionModal() {
  showEditFunctionModal.value = false
  editFunctionIdx.value = null
  editFunctionName.value = ''
}

// 停用/启用功能
const allFunctions = ref([
  { name: 'Home', status: 'Active', lastUpdated: '2025-07-03 10:00', lastUpdatedBy: 'Admin' },
  { name: 'Parameter', status: 'Active', lastUpdated: '2025-07-03 10:00', lastUpdatedBy: 'Admin' },
  { name: 'Run Management', status: 'Active', lastUpdated: '2025-07-03 10:00', lastUpdatedBy: 'Admin' },
  { name: 'Role Management', status: 'Active', lastUpdated: '2025-07-03 10:00', lastUpdatedBy: 'Admin' },
  { name: 'Audit Trial', status: 'Active', lastUpdated: '2025-07-03 10:00', lastUpdatedBy: 'Admin' },
])
const showAddFunctionRow = ref(false)
const newFunction = ref({ name: '', status: 'Active' })
const editFunctionIdxFunc = ref<number|null>(null)
const editFunctionNameFunc = ref('')

function addNewFunctionRow() {
  showAddFunctionRow.value = true
  newFunction.value = { name: '', status: 'Active' }
}
function saveNewFunction() {
  if (!newFunction.value.name) return
  allFunctions.value.push({
    ...newFunction.value,
    lastUpdated: new Date().toISOString(),
    lastUpdatedBy: 'Admin'
  })
  showAddFunctionRow.value = false
}
function cancelAddFunctionRow() {
  showAddFunctionRow.value = false
}
function openEditFunctionModalFunc(idx: number) {
  editFunctionIdxFunc.value = idx
  editFunctionNameFunc.value = allFunctions.value[idx].name
  showEditFunctionModal.value = true
}

// 角色功能维护相关变量
const roleFunctionEditStatus = ref('Active')
const newFunctionName = ref('')

function saveEditFunctionMapping() {
  if (
    selectedRole.value &&
    editFunctionName.value.trim()
  ) {
    if (!roleFunctionStatusMap.value[selectedRole.value]) {
      roleFunctionStatusMap.value[selectedRole.value] = {}
    }
    
    if (roleFunctionEditStatus.value === 'Active') {
      roleFunctionStatusMap.value[selectedRole.value][editFunctionName.value.trim()] = 'Active'
    } else {
      roleFunctionStatusMap.value[selectedRole.value][editFunctionName.value.trim()] = 'Inactive'
    }
  }
  showEditFunctionModal.value = false
  editFunctionIdx.value = null
  editFunctionName.value = ''
}

function saveEditFunctionFunc() {
  if (
    editFunctionIdxFunc.value !== null &&
    editFunctionNameFunc.value.trim()
  ) {
    const originalFunctionName = allFunctions.value[editFunctionIdxFunc.value].name
    const newFunctionName = editFunctionNameFunc.value.trim()
    const newStatus = allFunctions.value[editFunctionIdxFunc.value].status
    
    // 更新function信息
    allFunctions.value[editFunctionIdxFunc.value].name = newFunctionName
    allFunctions.value[editFunctionIdxFunc.value].lastUpdated = new Date().toISOString()
    allFunctions.value[editFunctionIdxFunc.value].lastUpdatedBy = 'Admin'
    
    // 如果function状态变为Inactive，同步更新所有role下的该function状态
    if (newStatus === 'Inactive') {
      // 遍历所有role，将该function设置为Inactive
      Object.keys(roleFunctionStatusMap.value).forEach(roleName => {
        if (!roleFunctionStatusMap.value[roleName]) {
          roleFunctionStatusMap.value[roleName] = {}
        }
        roleFunctionStatusMap.value[roleName][newFunctionName] = 'Inactive'
      })
      
      // 如果function名称也改变了，需要更新旧名称的映射
      if (originalFunctionName !== newFunctionName) {
        Object.keys(roleFunctionStatusMap.value).forEach(roleName => {
          if (roleFunctionStatusMap.value[roleName] && roleFunctionStatusMap.value[roleName][originalFunctionName]) {
            delete roleFunctionStatusMap.value[roleName][originalFunctionName]
          }
        })
      }
      
      // TODO: 这里可以添加SQL保存逻辑
      console.log('Function status changed to Inactive, updating all role mappings:', {
        functionName: newFunctionName,
        status: newStatus,
        updatedMappings: roleFunctionStatusMap.value
      })
    }
  }
  showEditFunctionModal.value = false
  editFunctionIdxFunc.value = null
  editFunctionNameFunc.value = ''
}

function closeEditFunctionModalFunc() {
  showEditFunctionModal.value = false
  editFunctionIdxFunc.value = null
  editFunctionNameFunc.value = ''
}

function saveRoleFunctionMappings() {
  // TODO: Replace with actual SQL save operation
  // For now, just log the current mappings
  console.log('Saving role-function mappings to SQL:', roleFunctionStatusMap.value)
  
  // You can add your SQL save logic here later
  // Example:
  // await saveRoleFunctionMappingsToDatabase(selectedRole.value, roleFunctionStatusMap.value[selectedRole.value])
  
  // Show success message (you can replace this with a proper notification system)
  alert('Role-function mappings saved successfully!')
}
</script>

<style scoped>
.breadcrumb-nav {
  margin-bottom: 18px;
}
.breadcrumb-list {
  display: flex;
  align-items: center;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 18px;
  color: #555;
}
.breadcrumb-list li:not(:last-child)::after {
  content: '>';
  margin: 0 6px;
  color: #bbb;
}
.config-outer-box {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(21,61,119,0.06);
  padding: 0 0 30px 0;
  margin-bottom: 40px;
  position: relative;
}
.config-inner-box {
  padding: 30px 30px 0 30px;
}
.upload-title {
  font-size: 18px;
  font-weight: bold;
  color: #153D77;
  margin-bottom: 24px;
}
.select-input-full {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #ddd;
  font-size: 14px;
  width: 100%;
  box-sizing: border-box;
}
.step-btn {
  padding: 10px 28px;
  background: #f0f0f0;
  color: #333;
  border-radius: 20px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.3s;
  margin: 0 5px;
}
.step-btn:hover {
  background: #e0e0e0;
}
.step-btn:disabled {
  background: #eee;
  color: #bbb;
  cursor: not-allowed;
}
.upload-button {
  padding: 12px 24px;
  background: #FF612C;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.3s;
  margin-top: 0;
}
.upload-button:hover {
  filter: brightness(90%);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}
</style>
