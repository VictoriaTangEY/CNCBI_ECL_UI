<template>
  <div style="display: flex; min-height: 100vh; margin-top: 95px;">
    <!-- 左侧导航菜单 -->
    <aside style="width: 280px; background-color: #f5f5f5; padding: 30px 20px;">
      <h3 style="font-weight: bold; font-size: 22px; margin-bottom: 24px;">Role Management</h3>
      <ul style="list-style: none; padding-left: 0;">
        <li @click="currentTab = 'user'" :style="{ cursor: 'pointer', color: currentTab === 'user' ? '#ff612c' : '#333', fontWeight: currentTab === 'user' ? '600' : 'normal', marginBottom: '10px', fontSize: '20px' }">▸ User Maintenance</li>
        <li @click="currentTab = 'role'" :style="{ cursor: 'pointer', color: currentTab === 'role' ? '#ff612c' : '#333', fontWeight: currentTab === 'role' ? '600' : 'normal', marginBottom: '10px', fontSize: '20px' }">▸ Role Maintenance</li>
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
          <li>{{ currentTab === 'user' ? 'User Maintenance' : currentTab === 'role' ? 'Role Maintenance' : currentTab === 'function' ? 'Function Maintenance' : 'Role-Function Maintenance' }}</li>
        </ol>
      </nav>

      <!-- User Maintenance -->
      <div class="config-outer-box" v-if="currentTab === 'user'">
        <div class="config-inner-box">
          <h2 class="upload-title">User Maintenance</h2>
          
          <!-- Query Section -->
          <div style="background: #f7f7f7; padding: 15px; margin-bottom: 20px; border-radius: 6px;">
            <div style="display: flex; gap: 15px; align-items: center;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-weight: 600; min-width: 80px;">User:</label>
                <input v-model="userQuery.user" placeholder="Enter user name" class="select-input-full" style="width: 200px;" />
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-weight: 600; min-width: 100px;">LoginName:</label>
                <input v-model="userQuery.loginName" placeholder="Enter login name" class="select-input-full" style="width: 200px;" />
              </div>
              <button class="step-btn" @click="queryUsers" style="background: #ff612c; color: white;">Query</button>
            </div>
          </div>

          <!-- Users Table -->
          <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e0e0e0;">
            <thead style="background: #f7f7f7;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Operation</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">User</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">LoginName</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Default Role</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">UpdatedBy</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Time</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(user, index) in filteredUsers" :key="index">
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="viewUser(user)" style="background: #007bff; color: white; padding: 6px 12px; font-size: 12px;">View</button>
                    <button class="step-btn" @click="updateUser(user)" style="background: #28a745; color: white; padding: 6px 12px; font-size: 12px;">Update</button>
                  </div>
                </td>
                <td style="padding: 12px; text-align: center; color: #007bff; cursor: pointer;">{{ user.userName }}</td>
                <td style="padding: 12px; text-align: center;">{{ user.loginName }}</td>
                <td style="padding: 12px; text-align: center;">{{ user.defaultRole }}</td>
                <td style="padding: 12px; text-align: center;">{{ user.updatedBy }}</td>
                <td style="padding: 12px; text-align: center;">{{ formatDate(user.time) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div style="margin-top: 15px; text-align: right;" v-if="currentTab === 'user'">
        <button class="upload-button" @click="showAddUserModal = true">Add New User</button>
      </div>

      <!-- Configuration Box with Progress Bar -->
      <div class="config-outer-box" v-if="currentTab === 'role'">
        <div class="config-inner-box">
          <h2 class="upload-title">Role Maintenance</h2>
          <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e0e0e0;">
            <thead style="background: #f7f7f7;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Actions</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Role Name</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Updated By</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Time</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(role, index) in roles" :key="index">
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="openRoleModal(true, role)">Edit</button>
                  </div>
                </td>
                <td style="padding: 12px; text-align: center; color: #007bff; cursor: pointer;">{{ role.roleName }}</td>
                <td :style="{ padding: '12px', textAlign: 'center', color: role.status === 'Active' ? '#4CAF50' : '#f44336' }">
                  {{ role.status === 'Inactive' ? 'D' : role.status }}
                </td>
                <td style="padding: 12px; text-align: center;">{{ role.updatedBy }}</td>
                <td style="padding: 12px; text-align: center;">{{ formatDate(role.time) }}</td>
              </tr>
              <tr v-if="showAddRow">
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="saveNewRole">Save</button>
                    <button class="step-btn" @click="cancelAddRow">Cancel</button>
                  </div>
                </td>
                <td style="padding: 12px; text-align: center;"><input v-model="newRole.roleName" placeholder="Role Name" class="select-input-full" style="text-align: center;" /></td>
                <td style="padding: 12px; text-align: center;">
                  <select v-model="newRole.status" class="select-input-full" style="text-align: center;">
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </td>
                <td style="padding: 12px; text-align: center;">-</td>
                <td style="padding: 12px; text-align: center;">-</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div style="margin-top: 15px; text-align: right;" v-if="currentTab === 'role'">
        <button class="upload-button" @click="addNewRoleRow">Add New Role</button>
      </div>
      <!-- Function Maintenance Table -->
      <div class="config-outer-box" v-if="currentTab === 'function'">
        <div class="config-inner-box">
          <h2 class="upload-title">Function Maintenance</h2>
          <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e0e0e0;">
            <thead style="background: #f7f7f7;">
              <tr>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Actions</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Function Name</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Status</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Updated By</th>
                <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Time</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(func, idx) in allFunctions" :key="idx">
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="openEditFunctionModalFunc(idx)">Edit</button>
                  </div>
                </td>
                <td style="padding: 12px; text-align: center; color: #007bff; cursor: pointer;">{{ func.name }}</td>
                <td :style="{ padding: '12px', textAlign: 'center', color: func.status === 'Active' ? '#4CAF50' : '#f44336' }">
                  {{ func.status === 'Inactive' ? 'D' : func.status }}
                </td>
                <td style="padding: 12px; text-align: center;">{{ func.updatedBy }}</td>
                <td style="padding: 12px; text-align: center;">{{ formatDate(func.time) }}</td>
              </tr>
              <tr v-if="showAddFunctionRow">
                <td style="padding: 12px; text-align: center;">
                  <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="step-btn" @click="saveNewFunction">Save</button>
                    <button class="step-btn" @click="cancelAddFunctionRow">Cancel</button>
                  </div>
                </td>
                <td style="padding: 12px; text-align: center;"><input v-model="newFunction.name" placeholder="Function Name" class="select-input-full" style="text-align: center;" /></td>
                <td style="padding: 12px; text-align: center;">
                  <select v-model="newFunction.status" class="select-input-full" style="text-align: center;">
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </td>
                <td style="padding: 12px; text-align: center;">-</td>
                <td style="padding: 12px; text-align: center;">-</td>
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
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Actions</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Function</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Status</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Updated By</th>
                  <th style="padding: 12px; border-bottom: 1px solid #ddd; text-align: center;">Time</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(func, idx) in allFunctions" :key="idx">
                  <td style="padding: 12px; text-align: center;">
                    <div style="display: flex; gap: 10px; justify-content: center;">
                      <button class="step-btn" @click="openEditFunctionModal(idx)">Edit</button>
                    </div>
                  </td>
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
                  <td style="padding: 12px; text-align: center;">{{ func.updatedBy }}</td>
                  <td style="padding: 12px; text-align: center;">{{ formatDate(func.time) }}</td>
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

      <!-- Add New User Modal -->
      <div v-if="showAddUserModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000;">
        <div style="background: white; padding: 20px; width: 400px; border-radius: 10px;">
          <h3>Add New User</h3>
          <div style="margin-top: 15px;">
            <label style="display: block; margin-bottom: 5px; font-weight: 600;">User ID:</label>
            <input v-model="newUserForm.userId" placeholder="Enter User ID" class="select-input-full" />
            <div style="margin-top: 10px; color: #666; font-size: 12px;">
              Enter the Active Directory User ID to validate and create new user
            </div>
          </div>
          <div style="margin-top: 15px; text-align: right;">
            <button class="step-btn" @click="validateAndAddUser" style="background: #ff612c; color: white;">Validate & Add</button>
            <button class="step-btn" @click="closeAddUserModal">Cancel</button>
          </div>
        </div>
      </div>

      <!-- Update User Modal -->
      <div v-if="showUpdateUserModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000;">
        <div style="background: white; padding: 20px; width: 500px; border-radius: 10px; max-height: 80vh; overflow-y: auto;">
          <h3>Update User</h3>
          <div style="margin-top: 15px;">
            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">User:</label>
                <input v-model="updateUserForm.userName" placeholder="User Name" class="select-input-full" />
              </div>
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">LoginName:</label>
                <input v-model="updateUserForm.loginName" placeholder="Login Name" class="select-input-full" disabled />
              </div>
            </div>
            
            <div style="margin-bottom: 15px;">
              <label style="display: block; margin-bottom: 5px; font-weight: 600;">Role:</label>
              <div style="max-height: 150px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">
                <div v-for="role in roles" :key="role.roleId" style="margin-bottom: 8px;">
                  <label style="display: flex; align-items: center; cursor: pointer;">
                    <input 
                      type="radio" 
                      :value="role.roleName" 
                      v-model="updateUserForm.defaultRole"
                      style="margin-right: 8px;"
                    />
                    {{ role.roleName }}
                  </label>
                </div>
              </div>
            </div>

            <div style="margin-bottom: 15px;">
              <label style="display: block; margin-bottom: 5px; font-weight: 600;">Email:</label>
              <input v-model="updateUserForm.email" placeholder="Email" class="select-input-full" />
            </div>

            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">Mobile No.:</label>
                <input v-model="updateUserForm.mobileNo" placeholder="Mobile Number" class="select-input-full" />
              </div>
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">Phone No.:</label>
                <input v-model="updateUserForm.phoneNo" placeholder="Phone Number" class="select-input-full" />
              </div>
            </div>

            <div style="margin-bottom: 15px;">
              <label style="display: block; margin-bottom: 5px; font-weight: 600;">Remark:</label>
              <textarea v-model="updateUserForm.remark" placeholder="Remark" class="select-input-full" style="min-height: 80px; resize: vertical;"></textarea>
            </div>
          </div>
          <div style="margin-top: 15px; text-align: right;">
            <button class="step-btn" @click="saveUserUpdate" style="background: #ff612c; color: white;">Submit</button>
            <button class="step-btn" @click="closeUpdateUserModal">Cancel</button>
          </div>
        </div>
      </div>

      <!-- View User Modal -->
      <div v-if="showViewUserModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000;">
        <div style="background: white; padding: 20px; width: 500px; border-radius: 10px;">
          <h3>View User Details</h3>
          <div style="margin-top: 15px;">
            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">User:</label>
                <div style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9;">{{ viewUserForm.userName }}</div>
              </div>
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">LoginName:</label>
                <div style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9;">{{ viewUserForm.loginName }}</div>
              </div>
            </div>
            
            <div style="margin-bottom: 15px;">
              <label style="display: block; margin-bottom: 5px; font-weight: 600;">Default Role:</label>
              <div style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9;">{{ viewUserForm.defaultRole }}</div>
            </div>

            <div style="margin-bottom: 15px;">
              <label style="display: block; margin-bottom: 5px; font-weight: 600;">Email:</label>
              <div style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9;">{{ viewUserForm.email || '-' }}</div>
            </div>

            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">Mobile No.:</label>
                <div style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9;">{{ viewUserForm.mobileNo || '-' }}</div>
              </div>
              <div style="flex: 1;">
                <label style="display: block; margin-bottom: 5px; font-weight: 600;">Phone No.:</label>
                <div style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9;">{{ viewUserForm.phoneNo || '-' }}</div>
              </div>
            </div>

            <div style="margin-bottom: 15px;">
              <label style="display: block; margin-bottom: 5px; font-weight: 600;">Remark:</label>
              <div style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9; min-height: 60px;">{{ viewUserForm.remark || '-' }}</div>
            </div>
          </div>
          <div style="margin-top: 15px; text-align: right;">
            <button class="step-btn" @click="closeViewUserModal">Close</button>
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
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'
import { getUserDisplayName } from '../services/authService'

const currentTab = ref('user')
const showRoleModal = ref(false)
const isEditing = ref(false)
const showAddRow = ref(false)
const newRole = ref({ roleName: '', roleId: '', status: 'Active' })
const roleForm = ref({ roleName: '', roleId: '', status: 'Active', remark: '' })
const originalRoleId = ref('')

// User Management Variables
const userQuery = ref({ user: '', loginName: '' })
const filteredUsers = ref<any[]>([])
const users = ref<any[]>([])
const showAddUserModal = ref(false)
const showUpdateUserModal = ref(false)
const showViewUserModal = ref(false)
const newUserForm = ref({ userId: '' })
const updateUserForm = ref({
  id: '',
  userName: '',
  loginName: '',
  defaultRole: '',
  email: '',
  mobileNo: '',
  phoneNo: '',
  remark: ''
})
const viewUserForm = ref({
  userName: '',
  loginName: '',
  defaultRole: '',
  email: '',
  mobileNo: '',
  phoneNo: '',
  remark: ''
})

// Role Management Variables
const roles = ref<any[]>([])
const activeRoles = ref<string[]>([])
const selectedRole = ref('')

// Function Management Variables
const allFunctions = ref<any[]>([])
const showAddFunctionRow = ref(false)
const newFunction = ref({ name: '', status: 'Active' })
const editFunctionIdxFunc = ref<number|null>(null)
const editFunctionNameFunc = ref('')

// Role-Function Management Variables
const roleFunctionStatusMap = ref<{ [role: string]: { [funcName: string]: string } }>({})
const showEditFunctionModal = ref(false)
const showAddFunctionModal = ref(false)
const editFunctionName = ref('')
const editFunctionIdx = ref<number|null>(null)
const roleFunctionEditStatus = ref('Active')
const newFunctionName = ref('')

// Load data from database
const loadUserRecords = async () => {
  try {
    const response = await axios.get('/api/get_user_records')
    if (response.data.status === 'success') {
      users.value = response.data.records
filteredUsers.value = users.value
    }
  } catch (error) {
    console.error('Error loading user records:', error)
  }
}

const loadRoleRecords = async () => {
  try {
    const response = await axios.get('/api/get_role_records')
    if (response.data.status === 'success') {
      roles.value = response.data.records
      activeRoles.value = roles.value.filter(role => role.status === 'Active').map(role => role.roleName)
    }
  } catch (error) {
    console.error('Error loading role records:', error)
  }
}

const loadFunctionRecords = async () => {
  try {
    const response = await axios.get('/api/get_function_records')
    if (response.data.status === 'success') {
      allFunctions.value = response.data.records
    }
  } catch (error) {
    console.error('Error loading function records:', error)
  }
}

const loadRoleFunctionRecords = async (roleName: string) => {
  try {
    const response = await axios.get(`/api/get_role_function_records/${roleName}`)
    if (response.data.status === 'success') {
      const records = response.data.records
      if (!roleFunctionStatusMap.value[roleName]) {
        roleFunctionStatusMap.value[roleName] = {}
      }
      records.forEach((record: any) => {
        roleFunctionStatusMap.value[roleName][record.functionName] = record.status
      })
    }
  } catch (error) {
    console.error('Error loading role-function records:', error)
  }
}

// Initialize data when component mounts
onMounted(async () => {
  await loadUserRecords()
  await loadRoleRecords()
  await loadFunctionRecords()
})

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// User Management Functions
function queryUsers() {
  const userFilter = userQuery.value.user.toLowerCase()
  const loginFilter = userQuery.value.loginName.toLowerCase()
  
  filteredUsers.value = users.value.filter(user => {
    const matchesUser = !userFilter || user.userName.toLowerCase().includes(userFilter)
    const matchesLogin = !loginFilter || user.loginName.toLowerCase().includes(loginFilter)
    return matchesUser && matchesLogin
  })
}

function viewUser(user: any) {
  viewUserForm.value = { ...user }
  showViewUserModal.value = true
}

function updateUser(user: any) {
  updateUserForm.value = { ...user }
  showUpdateUserModal.value = true
}

function closeAddUserModal() {
  showAddUserModal.value = false
  newUserForm.value = { userId: '' }
}

function closeUpdateUserModal() {
  showUpdateUserModal.value = false
  updateUserForm.value = {
    id: '',
    userName: '',
    loginName: '',
    defaultRole: '',
    email: '',
    mobileNo: '',
    phoneNo: '',
    remark: ''
  }
}

function closeViewUserModal() {
  showViewUserModal.value = false
  viewUserForm.value = {
    userName: '',
    loginName: '',
    defaultRole: '',
    email: '',
    mobileNo: '',
    phoneNo: '',
    remark: ''
  }
}

async function validateAndAddUser() {
  if (!newUserForm.value.userId.trim()) {
    alert('Please enter a User ID')
    return
  }

  console.log('Attempting to validate user ID:', newUserForm.value.userId)
  
  try {
    const requestBody = { user_id: newUserForm.value.userId }
    console.log('Sending request to backend:', requestBody)
    
    const response = await fetch('/api/validate-ad-user', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    })

    console.log('Response status:', response.status)
    console.log('Response headers:', response.headers)

    const result = await response.json()
    console.log('Response result:', result)

    if (response.ok && result.status === 'success') {
      // User exists in AD, create new ECL user record
      const newUser = {
        user_name: result.display_name || newUserForm.value.userId,
        login_name: newUserForm.value.userId,
        default_role: 'Unassigned',
        updated_by: getUserDisplayName(),
        time: new Date().toISOString(),
        email: result.email || '',
        mobile_no: '',
        phone_no: '',
        remark: ''
      }
      
      // Save to database
      console.log('Sending user data to backend:', newUser)
      const saveResponse = await axios.post('/api/save_user_record', newUser)
      if (saveResponse.data.status === 'success') {
        await loadUserRecords() // Reload data
      closeAddUserModal()
      } else {
        alert('Failed to save user record')
      }
    } else {
      alert(`Invalid user ID - ${result.message}`)
    }
  } catch (error) {
    console.error('Error validating user:', error)
    alert('Error connecting to Active Directory. Please try again.')
  }
}

async function saveUserUpdate() {
  try {
    const updateData = {
      user_id: updateUserForm.value.id,
      user_name: updateUserForm.value.userName,
      default_role: updateUserForm.value.defaultRole,
      email: updateUserForm.value.email,
      mobile_no: updateUserForm.value.mobileNo,
      phone_no: updateUserForm.value.phoneNo,
      remark: updateUserForm.value.remark,
      updated_by: getUserDisplayName()
    }
    
    const response = await axios.post('/api/update_user_record', updateData)
    if (response.data.status === 'success') {
      await loadUserRecords() // Reload data
    closeUpdateUserModal()
    } else {
      alert('Failed to update user record')
    }
  } catch (error) {
    console.error('Error updating user:', error)
    alert('Error updating user record')
  }
}

function getFunctionStatusForRole(roleName: string, functionName: string): string {
  return roleFunctionStatusMap.value[roleName]?.[functionName] || 'Inactive'
}

function openRoleModal(edit: boolean, role: any = null) {
  isEditing.value = edit
  if (edit && role) {
    roleForm.value = { ...role, remark: '' }
    originalRoleId.value = role.id
  } else {
    roleForm.value = { roleName: '', roleId: '', status: 'Active', remark: '' }
    originalRoleId.value = ''
  }
  showRoleModal.value = true
}

function closeRoleModal() {
  showRoleModal.value = false
}

async function saveRole() {
  try {
  if (isEditing.value) {
      const updateData = {
        role_id: originalRoleId.value,
        role_name: roleForm.value.roleName,
        status: roleForm.value.status,
        updated_by: getUserDisplayName()
      }
      
      const response = await axios.post('/api/update_role_record', updateData)
      if (response.data.status === 'success') {
        await loadRoleRecords() // Reload data
        closeRoleModal()
        } else {
        alert('Failed to update role record')
      }
    } else {
      const newRoleData = {
        role_name: roleForm.value.roleName,
        status: roleForm.value.status,
        updated_by: getUserDisplayName(),
        time: new Date().toISOString()
      }
      
      const response = await axios.post('/api/save_role_record', newRoleData)
      if (response.data.status === 'success') {
        await loadRoleRecords() // Reload data
        closeRoleModal()
  } else {
        alert('Failed to create role record')
    }
    }
  } catch (error) {
    console.error('Error saving role:', error)
    alert('Error saving role record')
  }
}

function addNewRoleRow() {
  showAddRow.value = true
  newRole.value = { roleName: '', roleId: '', status: 'Active' }
}

async function saveNewRole() {
  if (!newRole.value.roleName) return
  
  try {
    const newRoleData = {
      role_name: newRole.value.roleName,
      status: newRole.value.status,
      updated_by: getUserDisplayName(),
      time: new Date().toISOString()
    }
    
    const response = await axios.post('/api/save_role_record', newRoleData)
    if (response.data.status === 'success') {
      await loadRoleRecords() // Reload data
  showAddRow.value = false
    } else {
      alert('Failed to create role record')
    }
  } catch (error) {
    console.error('Error creating role:', error)
    alert('Error creating role record')
  }
}

function cancelAddRow() {
  showAddRow.value = false
}

// Function Management Functions
function addNewFunctionRow() {
  showAddFunctionRow.value = true
  newFunction.value = { name: '', status: 'Active' }
}

async function saveNewFunction() {
  if (!newFunction.value.name) return
  
  try {
    const newFunctionData = {
      function_name: newFunction.value.name,
      status: newFunction.value.status,
      updated_by: getUserDisplayName(),
      time: new Date().toISOString()
    }
    
    const response = await axios.post('/api/save_function_record', newFunctionData)
    if (response.data.status === 'success') {
      await loadFunctionRecords() // Reload data
      showAddFunctionRow.value = false
    } else {
      alert('Failed to create function record')
    }
  } catch (error) {
    console.error('Error creating function:', error)
    alert('Error creating function record')
  }
}

function cancelAddFunctionRow() {
  showAddFunctionRow.value = false
}

function openEditFunctionModalFunc(idx: number) {
  editFunctionIdxFunc.value = idx
  editFunctionNameFunc.value = allFunctions.value[idx].name
  showEditFunctionModal.value = true
}

async function saveEditFunctionFunc() {
  if (editFunctionIdxFunc.value !== null && editFunctionNameFunc.value.trim()) {
    try {
      const updateData = {
        function_id: allFunctions.value[editFunctionIdxFunc.value].id,
        function_name: editFunctionNameFunc.value.trim(),
        status: allFunctions.value[editFunctionIdxFunc.value].status,
        updated_by: getUserDisplayName()
      }
      
      const response = await axios.post('/api/update_function_record', updateData)
      if (response.data.status === 'success') {
        await loadFunctionRecords() // Reload data
        showEditFunctionModal.value = false
        editFunctionIdxFunc.value = null
        editFunctionNameFunc.value = ''
      } else {
        alert('Failed to update function record')
      }
    } catch (error) {
      console.error('Error updating function:', error)
      alert('Error updating function record')
    }
  }
}

function closeEditFunctionModalFunc() {
  showEditFunctionModal.value = false
  editFunctionIdxFunc.value = null
  editFunctionNameFunc.value = ''
}

// Role-Function Management Functions
async function loadRoleFunctionData(roleName: string) {
  if (roleName) {
    await loadRoleFunctionRecords(roleName)
  }
}

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

function openEditFunctionModal(idx: number) {
  editFunctionIdx.value = idx
  editFunctionName.value = allFunctions.value[idx].name
  roleFunctionEditStatus.value = getFunctionStatusForRole(selectedRole.value, editFunctionName.value)
  showEditFunctionModal.value = true
}

function closeEditFunctionModal() {
  showEditFunctionModal.value = false
  editFunctionIdx.value = null
  editFunctionName.value = ''
}

async function saveEditFunctionMapping() {
  if (selectedRole.value && editFunctionName.value.trim()) {
    try {
      const updateData = {
        role_name: selectedRole.value,
        function_name: editFunctionName.value.trim(),
        status: roleFunctionEditStatus.value,
        updated_by: getUserDisplayName()
      }
      
      const response = await axios.post('/api/update_role_function_record', updateData)
      if (response.data.status === 'success') {
        await loadRoleFunctionRecords(selectedRole.value) // Reload data
  showEditFunctionModal.value = false
  editFunctionIdx.value = null
  editFunctionName.value = ''
      } else {
        alert('Failed to update role-function mapping')
      }
    } catch (error) {
      console.error('Error updating role-function mapping:', error)
      alert('Error updating role-function mapping')
    }
  }
}

async function saveRoleFunctionMappings() {
  try {
    // Save all role-function mappings for the selected role
    const mappings = roleFunctionStatusMap.value[selectedRole.value] || {}
    const promises = Object.entries(mappings).map(([functionName, status]) => {
      const mappingData = {
        role_name: selectedRole.value,
        function_name: functionName,
        status: status,
        updated_by: getUserDisplayName(),
        time: new Date().toISOString()
    }
      return axios.post('/api/save_role_function_record', mappingData)
    })
    
    await Promise.all(promises)
  } catch (error) {
    console.error('Error saving role-function mappings:', error)
    alert('Error saving role-function mappings')
  }
}

// Watch for role selection changes
watch(selectedRole, (newRole) => {
  if (newRole) {
    loadRoleFunctionData(newRole)
}
})
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
