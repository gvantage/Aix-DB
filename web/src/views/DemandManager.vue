***REMOVED***
    <LayoutCenterPanel :loading="loading">
        <n-layout
            style="
                height: 99%;
              ***REMOVED***
              ***REMOVED***
                margin-right: 2px;
            "
        >
            <n-layout-header class="header">
      ***REMOVED***class="header-content">
                    <!-- 这里可以放置一些顶部的内容或导航 -->
    ***REMOVED***
                <button class="create-project-btn" @click="showModal = true">
                    + 创建项目
      ***REMOVED***
            </n-layout-header>
            <n-layout-content>
      ***REMOVED***class="container">
                    <div
                        class="card"
                        v-for="(item, index***REMOVED*** in items"
                        :key="index"
          ***REMOVED***
              ***REMOVED***class="card-header">
                            <n-icon style="margin-right: 5px" size="18">
                      ***REMOVED***class="i-formkit:filedoc"></div>
                            </n-icon>
                            <span class="card-title">需求</span>
            ***REMOVED***
              ***REMOVED***class="card-body">
                            <p>{{ item.doc_desc ***REMOVED******REMOVED***</p>
            ***REMOVED***
              ***REMOVED***class="card-footer">
                            <span class="card-info"
                      ***REMOVED***抽取功能: {{ item.fun_num ***REMOVED******REMOVED***</span
                  ***REMOVED***
                            <span class="card-date">{{
                                item.create_time
                            ***REMOVED******REMOVED***</span>
                            <!-- 使用 n-dropdown 组件替换原有的按钮 -->
                            <n-dropdown
                                trigger="click"
                                :options="dropdownOptions"
                                @select="(key***REMOVED*** => handleSelect(key, index***REMOVED***"
                  ***REMOVED***
                                <button class="card-button">...</button>
                            </n-dropdown>
            ***REMOVED***
        ***REMOVED***
    ***REMOVED***
            </n-layout-content>
      ***REMOVED***

        <!-- 模态框 -->
        <n-modal
            v-model:show="showModal"
            preset="dialog"
            title="创建新项目"
            style="width: 600px"
            @close="closeModal"
        >
            <n-form :model="projectForm">
                <n-form-item label="项目名称" required>
                    <n-input
                        v-model:value="projectForm.doc_name"
                        placeholder="请输入项目名称"
          ***REMOVED***
                </n-form-item>
                <n-form-item label="项目描述" required>
                    <n-input
                        v-model:value="projectForm.doc_desc"
                        type="textarea"
                        placeholder="请输入项目描述"
          ***REMOVED***
                </n-form-item>
                <n-form-item label="项目附件" hidden>
                    <n-input v-model:value="projectForm.file_key" />
                </n-form-item>
                <n-upload
                    multiple
                    :show-file-list="true"
                    action="sanic/file/upload_file"
                    accept=".doc, .docx"
                    ref="uploadDocRef"
                    @finish="finish_upload"
      ***REMOVED***
                    <n-button>上传附件</n-button>
                </n-upload>
            </n-form>
            <template #action>
                <n-button @click="submitProject">提交</n-button>
                <n-button @click="closeModal">取消</n-button>
            ***REMOVED***
        </n-modal>
    </LayoutCenterPanel>
***REMOVED***

<script setup>
import { ref ***REMOVED*** from 'vue'
import { NLayout, NLayoutHeader, NLayoutContent ***REMOVED*** from 'naive-ui'
import * as GlobalAPI from '@/api'

const loading = ref(true***REMOVED***

const uploadDocRef = ref(***REMOVED***
const finish_upload = (res***REMOVED*** => {
    if (res.event.target.responseText***REMOVED*** {
        let json_data = JSON.parse(res.event.target.responseText***REMOVED***
        let file_key = json_data['data']['object_key']
        if (json_data['code'] == 200***REMOVED*** {
            window.$ModalMessage.success(`文件上传成功`***REMOVED***
            projectForm.value.file_key = file_key
            projectForm.value.doc_name = file_key.split('.'***REMOVED***[0]
            projectForm.value.doc_desc = file_key.split('.'***REMOVED***[0]
        ***REMOVED*** else {
            window.$ModalMessage.error(`文件上传失败`***REMOVED***
            return
        ***REMOVED***
    ***REMOVED***
***REMOVED***

const showModal = ref(false***REMOVED***
const items = ref([]***REMOVED***

const projectForm = ref({
    doc_name: '',
    doc_desc: '',
    file_key: ''
***REMOVED******REMOVED***
const submitProject = async (***REMOVED*** => {
    const res = await GlobalAPI.insert_demand_manager(projectForm.value***REMOVED***
    const json = await res.json(***REMOVED***
    if (json?.data !== undefined && json?.data***REMOVED*** {
        window.$ModalMessage.success(`项目创建成功`***REMOVED***
        closeModal(***REMOVED***
    ***REMOVED***

    query_demand_records(***REMOVED***
***REMOVED***

const closeModal = (***REMOVED*** => {
    showModal.value = false
    // 清空表单
    projectForm.value = {
        doc_name: '',
        doc_desc: '',
        file_key: ''
    ***REMOVED***
***REMOVED***

const dropdownOptions = [
  ***REMOVED***
        label: '编辑',
        key: 'edit'
    ***REMOVED***,
  ***REMOVED***
        label: '删除',
        key: 'delete'
    ***REMOVED***
    // 可以根据需要添加更多选项
]

const handleSelect = async (key, index***REMOVED*** => {
    switch (key***REMOVED*** {
        case 'edit':
            console.log(`Editing item at index ${index***REMOVED***`***REMOVED***
            // 编辑项目的逻辑
            break
        case 'delete':
            // if (confirm('确定要删除此项目吗？'***REMOVED******REMOVED*** {
            GlobalAPI.delete_demand_records(items.value[index].id***REMOVED***
            await query_demand_records(***REMOVED***
            // ***REMOVED***
            break
        default:
            console.log(`Selected option not handled: ${key***REMOVED***`***REMOVED***
    ***REMOVED***
***REMOVED***

const query_demand_records = async (***REMOVED*** => {
    const res = await GlobalAPI.query_demand_records(1, 999999***REMOVED***
    const json = await res.json(***REMOVED***
    if (json?.data !== undefined***REMOVED*** {
        items.value = json.data.records
    ***REMOVED***
    ***REMOVED*** else {
        items.value = []
    ***REMOVED***
***REMOVED***

onMounted((***REMOVED*** => {
    query_demand_records(***REMOVED***
***REMOVED******REMOVED***
***REMOVED***

***REMOVED***
.header {
  ***REMOVED***
    justify-content: space-between;
    align-items: center;
  ***REMOVED*** /* 调整padding以适应设计 */
    background-color: #f6f7fb; /* 根据需要调整背景颜色 */
***REMOVED***

.header-content {
    /* 这里可以添加任何必要的样式，比如logo或导航链接 */
***REMOVED***

.create-project-btn {
    background-color: #2c7be5;
    color: #fff;
  ***REMOVED***
  ***REMOVED***
    border-radius: 20px;
  ***REMOVED***
    font-size: 14px;
***REMOVED***

.container {
  ***REMOVED***
    flex-wrap: wrap;
    gap: 20px;
  ***REMOVED***
***REMOVED***

.card {
    width: 250px;
    margin-top: 40px;
  ***REMOVED***
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1***REMOVED***;
    background-color: #ffffff;
    overflow: hidden;
***REMOVED***

.card-header {
  ***REMOVED***
    align-items: center;
  ***REMOVED***
    background-color: #f9f9f9;
***REMOVED***

.card-icon {
    width: 20px;
    height: 20px;
  ***REMOVED***
***REMOVED***

.card-title {
    font-weight: bold;
***REMOVED***

.card-body {
  ***REMOVED***
***REMOVED***

.card-footer {
  ***REMOVED***
    justify-content: space-between;
  ***REMOVED***
  ***REMOVED***
***REMOVED***

.card-info,
.card-date {
    font-size: 12px;
  ***REMOVED***
***REMOVED***

.card-button {
    background-color: #e0e0e0;
  ***REMOVED***
    padding: 5px 10px;
  ***REMOVED***
  ***REMOVED***
    font-size: 12px;
***REMOVED***

form-item-inline {
  ***REMOVED***
    align-items: center;
***REMOVED***

.form-item-inline .n-form-item__label {
    width: 120px; /* 设置标签宽度 */
    margin-right: 15px; /* 设置标签与输入框之间的间距 */
***REMOVED***
***REMOVED***
