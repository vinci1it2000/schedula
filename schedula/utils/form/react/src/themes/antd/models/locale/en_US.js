import en_US from 'antd/locale/en_US';

export const locale = {
    ...en_US,
    App: {
        runButton: "Run",
        debugButton: "Debug",
        cleanButton: "Clean",
        cleanConfirm: "Sure to delete this data?",
        fullscreenButton: "Fullscreen",
        enableFullscreen: "Enable Fullscreen",
        disableFullscreen: "Disable Fullscreen",
        filesButton: "Files",
        downloadButton: "Download",
        downloadTooltip: "Export data as JSON",
        uploadButton: "Upload",
        uploadTooltip: "Import data as JSON",
        cloudButton: "Cloud",
        cloudUploadTooltip: "Save data to Cloud",
        cloudUploadButton: "Save",
        cloudDownloadTooltip: "Import data from Cloud",
        cloudDownloadButton: "Import",
        autoSavingButton: "AutoSaving",
        autoSavingTooltip: "Disable AutoSaving",
        autoSaveButton: "AutoSave",
        autoSaveTooltip: "Enable AutoSaving",
        autoSavingErrorTitle: 'Ops... disabling auto-saving',
        restoreButton: "Restore",
        restoreTooltip: "Restore data",
        restoreModalTitle: "Restore data",
        restoreEraseButton: "Erase storage",
        restoreCloseButton: "Close",
        restoreCurrent: "current",
        restoreRestoreButton: "Restore",
        restoreConfirm: "Sure to restore this data?",
        restoreDifferences: "Show differences from current data",
        restoreTitleDifferences: "Differences"
    },
    Contact: {
        buttonTooltip: "Contact",
        title: "Contact us",
        submitButton: "Send",
        namePlaceholder: "Your Name",
        nameRequired: "Please input your Name!",
        emailPlaceholder: "Email",
        emailRequired: "Please input your Email!",
        emailInvalid: "Invalid Email!",
        subjectPlaceholder: "Mail Subject",
        subjectRequired: "Please enter mail subject!",
        messagePlaceholder: "Your Message",
        messageRequired: "Please enter your message!",
        errorTitle: 'Ops... something went wrong!'
    },
    User: {
        buttonTooltip: "Login",
        titleInfo: "User info",
        titleLogin: "Login",
        titleLogout: "Sure to logout?",
        titleSetting: "Edit settings",
        titleForgot: "Recover password",
        titleRegister: "New registration",
        titleConfirm: "Send confirmation email",
        titleResetPassword: "Reset password",
        loginTooltip: 'Login',
        infoButton: 'Profile',
        settingButton: 'Settings',
        logoutButton: 'Logout'
    },
    "User.Login": {
        submitButton: "Login",
        or: "Or",
        registerNow: "register now!",
        emailPlaceholder: "Email",
        emailRequired: "Please input your Email!",
        emailInvalid: "Invalid Email!",
        sendConfirmMail: "resend confirmation email",
        passwordPlaceholder: "Password",
        passwordRequired: "Please input your Password!",
        rememberMe: "Remember me",
        forgotPassword: "Forgot password",
        errorTitle: 'Ops... something went wrong!'
    },
    "User.Logout": {
        submitButton: "Logout",
    },
    "User.Forgot": {
        submitButton: "Recover Password",
        or: "Or",
        login: "login!",
        emailPlaceholder: "Email",
        emailRequired: "Please input your Email!",
        emailInvalid: "Invalid Email!",
        errorTitle: 'Ops... something went wrong!'
    },
    "User.Confirm": {
        submitButton: "Send instructions",
        or: "Or",
        login: "login!",
        emailPlaceholder: "Email",
        emailRequired: "Please input your Email!",
        emailInvalid: "Invalid Email!",
        errorTitle: 'Ops... something went wrong!'
    },
    "User.ResetPassword": {
        or: "Or",
        login: "login!",
        submitButton: "Reset Password",
        passwordPlaceholder: "New Password",
        passwordRequired: "Please input your New Password!",
        passwordConfirmPlaceholder: "Confirm New Password",
        passwordConfirmRequired: "Please confirm your New Password!",
        passwordConfirmError: 'The two passwords that you entered do not match!',
        errorTitle: 'Ops... something went wrong!'
    },
    "User.Register": {
        submitButton: "Register",
        or: "Or",
        login: "login!",
        emailPlaceholder: "Email",
        emailRequired: "Please input your Email!",
        emailInvalid: "Invalid Email!",
        firstnamePlaceholder: "Name",
        firstnameRequired: "Please input your Name!",
        lastnamePlaceholder: "Surname",
        lastnameRequired: "Please input your Surname!",
        usernamePlaceholder: "Username",
        usernameRequired: "Please input your Username!",
        passwordPlaceholder: "Password",
        passwordRequired: "Please input your Password!",
        passwordConfirmPlaceholder: "Confirm Password",
        passwordConfirmRequired: "Please confirm your Password!",
        passwordConfirmError: 'The two passwords that you entered do not match!',
        errorTitle: 'Ops... something went wrong!'
    },
    "User.Setting": {
        errorTitle: 'Ops... something went wrong!',
        submitButton: 'Save',
        revertButton: 'Revert',
        firstnamePlaceholder: "Name",
        firstnameRequired: "Please input your Name!",
        lastnamePlaceholder: "Surname",
        lastnameRequired: "Please input your Surname!",
    },
    CloudDownloadField: {
        errorTitle: 'Ops... something went wrong!',
        fieldErrors: {name: 'Please input name!'},
        dataSwitchChecked: "current",
        dataSwitchUnChecked: "server",
        titleName: "Name",
        titleData: "Data Source",
        buttonDownload: "Server",
        buttonOverwrite: "Overwrite",
        createdAt: "Created",
        updatedAt: "Updated",
        confirmDelete: "Sure to delete?",
        buttonSaveNew: 'New record',
        buttonSave: "Save",
        buttonCancel: "Cancel",
        titleSaveNew: "Save current data"
    },
    CloudUploadField: {
        errorTitle: 'Ops... something went wrong!',
        fieldErrors: {name: 'Please input name!'},
        dataSwitchChecked: "current",
        dataSwitchUnChecked: "server",
        titleName: "Name",
        titleData: "Data Source",
        buttonDownload: "Server",
        buttonOverwrite: "Overwrite",
        createdAt: "Created",
        updatedAt: "Updated",
        confirmDelete: "Sure to delete?",
        buttonSaveNew: 'New record',
        buttonSave: "Save",
        buttonCancel: "Cancel",
        titleSaveNew: "Save current data"
    },
    FileWidget: {
        errorNotUploaded: 'Ops... file not uploaded',
        errorFileType: 'You can only upload {fileTypes} file!',
        errorMaxItems: 'You can upload maximum {maxItems} files!',
        errorOnlyOneItem: 'You can upload maximum one file!',
        errorSameFile: 'File {filename} already uploaded!',
        dropMessage: 'Drag File Here or Click to Browse',
        errorToolTip: "Upload Error"
    },
    DebugTemplate: {
        tooltipFloatButton: 'Open Debug Workflow',
        titleModal: 'Debug Workflow'
    },
    Errors: {
        title: "Validation Errors"
    },
    ErrorListTemplate: {
        tooltipFloatButton: 'Open Error Messages',
        descriptionFloatButton: "ERR",
        titleModal: 'Errors'
    },
    PDFField: {
        ...en_US.Upload, ...en_US.Image,
        titleSectionSelection: 'Sections'
    },
    ArrayAccordion: {
        ...en_US.global,
        tooltipExtra: "Copy data over",
        titleCopyButton: 'Please select where to copy data?'
    },
    ArrayCopy: {
        ...en_US.global,
        tooltip: "Copy data over",
        titleCopyButton: 'Please select where to copy data?'
    },
    TableField: {
        deleteAllConfirm: "Sure to delete all content?",
        deleteItemConfirm: "Sure to delete?",
        importTooltip: 'Import table from CSV',
        exportTooltip: "Export table in CSV",
        addItemTooltip: 'Add item'
    },
    TabsField: {
        clone: 'clone',
        moveup: 'move up',
        movedown: 'move down',
        moveleft: 'move left',
        moveright: 'move right',
        delete: 'delete',
        select: 'select',
        selectItem: 'Select item'
    }
}
export default locale