import en_US from 'antd/locale/en_US.js';
import merge from "lodash/merge.js";

const en = en_US.default
export const locale = merge({}, en, {
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
        branchesButton: "Branches",
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
        messageRequired: "Please enter your message!"
    },
    User: {
        buttonTooltip: "Login",
        titleInfo: "User info",
        titleLogin: "Login",
        titleLogout: "Sure to logout?",
        titleChangePassword: "Change password",
        titleSetting: "Edit settings",
        titleForgot: "Recover password",
        titleRegister: "New registration",
        titleConfirm: "Send confirmation email",
        titleResetPassword: "Reset password",
        loginTooltip: 'Login',
        infoButton: 'Profile',
        subscriptionButton: 'Subscription',
        changePasswordButton: 'Change password',
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
        forgotPassword: "Forgot password"
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
        emailInvalid: "Invalid Email!"
    },
    "User.Confirm": {
        submitButton: "Send instructions",
        or: "Or",
        login: "login!",
        emailPlaceholder: "Email",
        emailRequired: "Please input your Email!",
        emailInvalid: "Invalid Email!"
    },
    "User.ChangePassword": {
        submitButton: "Change Password",
        currentPasswordRequired: "Please input your Current Password!",
        currentPasswordPlaceholder: "Current password",
        passwordPlaceholder: "New Password",
        passwordRequired: "Please input your New Password!",
        passwordConfirmPlaceholder: "Confirm New Password",
        passwordConfirmRequired: "Please confirm your New Password!",
        passwordConfirmError: 'The two passwords that you entered do not match!'
    },
    "User.ResetPassword": {
        or: "Or",
        login: "login!",
        submitButton: "Reset Password",
        passwordPlaceholder: "New Password",
        passwordRequired: "Please input your New Password!",
        passwordConfirmPlaceholder: "Confirm New Password",
        passwordConfirmRequired: "Please confirm your New Password!",
        passwordConfirmError: 'The two passwords that you entered do not match!'
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
        passwordConfirmError: 'The two passwords that you entered do not match!'
    },
    "User.Setting": {
        submitButton: 'Save',
        revertButton: 'Revert',
        firstnamePlaceholder: "Name",
        firstnameRequired: "Please input your Name!",
        lastnamePlaceholder: "Surname",
        lastnameRequired: "Please input your Surname!",
    },
    "User.Settings": {
        submitButton: 'Save',
        revertButton: 'Revert'
    },
    CloudDownloadField: {
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
        titleSaveNew: "Save current data",
        tooltipButtonOverwrite: "Overwrite current data",
        tooltipButtonSaveNew: "Save current data",
        tooltipImport: "Import selected",
        tooltipConfirmEdit: "Confirm",
        tooltipCancelEdit: "Cancel",
        tooltipEditData: "Edit data",
        tooltipDelete: "Delete data",
        actions: "Actions"
    },
    CloudUploadField: {
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
    Cookies: {
        modalTitle: "Notice",
        saveButton: "Save and continue",
        acceptButton: "Accept",
        acceptAllButton: "Accept All",
        cancelButton: "Cancel",
        rejectButton: "Reject Optionals",
        rejectAllButton: "Reject All",
        settingsText: "Customize",
        settingsTitle: "Your consent preferences for tracking technologies",
        settingsIntro: "The options provided in this section allow you to customize your consent preferences for any tracking technology used for the purposes described below. To learn more about how these trackers help us and how they work, refer to the [cookie policy](/privacy). Please be aware that denying consent for a particular purpose may make related features unavailable.",
        introText: "We and selected third parties use cookies or similar technologies for technical purposes and, with your consent, for other purposes as specified in the Cookie Policy. For more information read our [Terms and Conditions](/terms-of-service) and [Cookie Policy](/privacy).",
        titleMandatory: "Necessary",
        descriptionMandatory: "These trackers are used for activities that are strictly necessary to operate or deliver the service you requested from us and, therefore, do not require you to consent.",
        titleFunctional: "Functionality",
        descriptionFunctional: "These trackers enable basic interactions and functionalities that allow you to access selected features of our service and facilitate your communication with us.",
        titleExperience: "Experience",
        descriptionExperience: "These trackers help us to improve the quality of your user experience and enable interactions with external content, networks and platforms.",
        titleMeasuring: "Measuring",
        descriptionMeasuring: "These trackers help us to measure traffic and analyze your behavior to improve our service.",
        titleMarketing: "Marketing",
        descriptionMarketing: "These trackers help us to deliver personalized ads or marketing content to you, and to measure their performance.",
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
        ...en.Upload, ...en.Image,
        titleSectionSelection: 'Sections'
    },
    "Stripe.Card": {
        titleFeatures: "Include:",
        buttonText: "Buy",
        modalTitle: "Checkout"
    },
    ArrayAccordion: {
        ...en.global,
        tooltipExtra: "Copy data over",
        titleCopyButton: 'Please select where to copy data?'
    },
    ArrayCopy: {
        ...en.global,
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
    },
    Calendar: {
        lang: {
            shortMonths: null,
            shortWeekDays: null,
            monthFormat: null,
        }
    },
    DatePicker: {
        lang: {
            shortMonths: null,
            shortWeekDays: null,
            monthFormat: null,
        }
    }
})
export default locale