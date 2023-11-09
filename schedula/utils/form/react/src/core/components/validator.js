import {customizeValidator} from "@rjsf/validator-ajv8";
import localizer from "ajv-i18n";

function defineValidator(language) {
    return customizeValidator({
        ajvOptionsOverrides: {
            $data: true,
            useDefaults: true,
            coerceTypes: true,
            validateSchema: false,
            code: {
                optimize: false
            }
        }
    }, localizer[language.split('_')[0]] || localizer.en)
}

export {defineValidator as default};
