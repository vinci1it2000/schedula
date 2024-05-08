import localizer from "ajv-i18n";
import {
    customizeValidator,
    createPrecompiledValidator
} from '@rjsf/validator-ajv8';
import {
    compileSchemaValidatorsCode
} from '@rjsf/validator-ajv8/dist/compileSchemaValidators';
import {evaluateValidator} from './precompile'
import hash from "object-hash";

function defineValidator(precompiledValidator, language, schema, nonce) {
    const options = {
        ajvOptionsOverrides: {
            $data: true,
            useDefaults: true,
            coerceTypes: true,
            validateSchema: false,
            code: {
                optimize: false
            }
        }
    }, local = localizer[language.split('_')[0]] || localizer.en
    if (precompiledValidator) {
        const code = compileSchemaValidatorsCode(schema, options);
        return evaluateValidator(hash(schema), code, nonce).then((precompiledValidator) => createPrecompiledValidator(
            precompiledValidator, schema, local
        ))
    } else {
        return new Promise((resolve) => resolve(customizeValidator(options, local)))
    }

}

export {defineValidator as default};
