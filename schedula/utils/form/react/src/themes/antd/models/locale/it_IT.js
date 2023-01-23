import it_IT from 'antd/locale/it_IT';

export const locale = {
    ...it_IT,
    App: {
        runButton: "Esegui",
        debugButton: "Debug",
        cleanButton: "Pulisci",
        cleanConfirm: "Sicuro di cancellare i dati?",
        fullscreenButton: "Fullscreen",
        enableFullscreen: "Abilita schermo intero",
        disableFullscreen: "Disabilita schermo intero",
        filesButton: "File",
        downloadButton: "Scarica",
        downloadTooltip: "Esporta i dati come JSON",
        uploadButton: "Carica",
        uploadTooltip: "Importa i dati come JSON",
        cloudButton: "Server",
        cloudUploadTooltip: "Salva i dati sul server",
        cloudUploadButton: "Salva",
        cloudDownloadTooltip: "Importa i dati dal server",
        cloudDownloadButton: "Importa",
        autoSavingButton: "AutoSaving",
        autoSavingTooltip: "Disabilita salvataggio automatico",
        autoSaveButton: "AutoSave",
        autoSavingErrorTitle: 'Ops... disattivando il salvataggio automatico',
        autoSaveTooltip: "Abilita salvataggio automatico",
        restoreButton: "Ripristina",
        restoreTooltip: "Ripristina i dati",
        restoreModalTitle: "Ripristina i dati",
        restoreEraseButton: "Cancella memoria",
        restoreCloseButton: "Chiudi",
        restoreCurrent: "corrente",
        restoreRestoreButton: "Ripristina",
        restoreConfirm: "Sicuro di ripristinare i dati?",
        restoreDifferences: "Mostra le differenze rispetto ai dati correnti",
        restoreTitleDifferences: "Differenze"
    },
    User: {
        buttonTooltip: "Accedi",
        titleInfo: "Informazioni utente",
        titleLogin: "Login",
        titleLogout: "Sicuro di uscire?",
        titleSetting: "Modifica le impostazioni",
        titleForgot: "Recupera la password",
        titleRegister: "Nuova registrazione",
        titleConfirm: "Invia la mail di conferma",
        titleResetPassword: "Resetta la password",
        loginTooltip: 'Accedi',
        infoButton: 'Profilo',
        settingsButton: 'Impostazioni',
        logoutButton: 'Uscire'
    },
    "User.Login": {
        submitButton: "Accedi",
        or: "O",
        registerNow: "registrati ora!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        sendConfirmMail: "invia nuovamente la mail di conferma",
        passwordPlaceholder: "Password",
        passwordRequired: "Inserisci la tua Password!",
        rememberMe: "Ricordami",
        forgotPassword: "Password dimenticata?",
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.Logout": {
        submitButton: "Esci",
    },
    "User.Forgot": {
        submitButton: "Recupera la Password",
        or: "O",
        login: "accedi!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        errorTitle: 'Ops... qualcosa è andata storta!',
    },
    "User.Confirm": {
        submitButton: "Invia le istruzioni",
        or: "O",
        login: "accedi!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.ResetPassword": {
        or: "O",
        login: "accedi!",
        submitButton: "Resetta la password",
        passwordPlaceholder: "Nuova Password",
        passwordRequired: "Inserisci la tua Nuova Password!",
        passwordConfirmPlaceholder: "Conferma la Nuova Password",
        passwordConfirmRequired: "Inserisci nuovamente la tua Nuova Password!",
        passwordConfirmError: 'Le due password che hai inserito non corrispondono!',
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.Register": {
        submitButton: "Registrati",
        or: "O",
        login: "accedi!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        firstnamePlaceholder: "Nome",
        firstnameRequired: "Inserisci il tuo Nome!",
        lastnamePlaceholder: "Cognome",
        lastnameRequired: "Inserisci il tuo Cognome!",
        usernamePlaceholder: "Nome utente",
        usernameRequired: "Inserisci il tuo Nome utente!",
        passwordPlaceholder: "Password",
        passwordRequired: "Inserisci la tua Password!",
        passwordConfirmPlaceholder: "Conferma la Password",
        passwordConfirmRequired: "Inserisci nuovamente la tua Password!",
        passwordConfirmError: 'Le due password che hai inserito non corrispondono!',
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.Settings": {
        errorTitle: 'Ops... qualcosa è andata storta!',
        saveButton: 'Salva',
        revertButton: 'Ripristina',
        firstnamePlaceholder: "Nome",
        firstnameRequired: "Inserisci il tuo Nome!",
        lastnamePlaceholder: "Cognome",
        lastnameRequired: "Inserisci il tuo Cognome!",
    },
    FileWidget: {
        errorNotUploaded: 'Ops... file non caricato',
        errorFileType: 'Puoi caricare solo file {fileTypes}!',
        errorMaxItems: 'Puoi caricare un massimo di {maxItems} file!',
        errorOnlyOneItem: 'Puoi caricare massimo un file!',
        errorSameFile: 'File {filename} già caricato!',
        dropMessage: 'Trascina il file qui o fai clic per cercare',
        errorToolTip: "Errore di caricamento"
    },
    DebugTemplate: {
        tooltipFloatButton: 'Apri il diagramma di debug',
        titleModal: 'Diagramma di debug'
    },
    Errors: {
        title: "Errori di Validazione"
    },
    ErrorListTemplate: {
        tooltipFloatButton: 'Apri i messaggi di errore',
        descriptionFloatButton: "ERR",
        titleModal: 'Errori'
    },
    PDFField: {
        ...it_IT.Upload, ...it_IT.Image,
        titleSectionSelection: 'Sezioni di stampa'
    },
    ArrayAccordion: {
        ...it_IT.global,
        tooltipExtra: "Copia dati",
        titleCopyButton: 'Seleziona dove copiare i dati?'
    },
    TableField: {
        deleteAllConfirm: "Sei sicuro di eliminare tutti i contenuti?",
        deleteItemConfirm: "Sicuro di eliminare?",
        importTooltip: 'Importa tabella da CSV',
        exportTooltip: "Esporta tabella in CSV",
        addItemTooltip: 'Aggiungi elemento'
    },
    TabsField: {
        clone: 'clona',
        moveup: 'sposta su',
        movedown: 'sposta giù',
        moveleft: 'sposta a sinistra',
        moveright: 'sposta a destra',
        delete: 'cancella',
        select: 'seleziona',
        selectItem: 'Seleziona elemento'
    }
}
export default locale