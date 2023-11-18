import i18n from 'i18next';
import Backend from 'i18next-http-backend';
import po2i18next from 'gettext-converter/po2i18next'

i18n.use(Backend).init({
    fallbackLng: 'en_US',
    lng: document.documentElement.lang,
    ns: 'messages',
    defaultNS: 'messages',
    parseMissingKeyHandler: (key) => (
        key.startsWith(`messages:`) ? key.slice(9) : key
    ),
    appendNamespaceToMissingKey: true,
    interpolation: {
        escapeValue: false, // not needed for react as it escapes by default
    },
    backend: {
        loadPath: '/locales/{{lng}}/{{ns}}',
        parse: function (data) {
            return po2i18next(data, {compatibilityJSON: 'v4'})
        }
    }
});
export default i18n;
