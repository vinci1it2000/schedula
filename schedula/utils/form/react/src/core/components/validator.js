import localizer from "ajv-i18n";
import {createPrecompiledValidator} from '@rjsf/validator-ajv8';
import {
    compileSchemaValidatorsCode
} from '@rjsf/validator-ajv8/dist/compileSchemaValidators';
import {evaluateValidator} from './precompile'
import hash from "object-hash";

function defineValidator(language, schema, nonce) {
    const code = compileSchemaValidatorsCode(schema, {
        $data: true,
        useDefaults: true,
        coerceTypes: true,
        validateSchema: false,
        code: {
            optimize: false
        }
    });
    return evaluateValidator(hash(schema), code, nonce).then((precompiledValidator) => createPrecompiledValidator(
        precompiledValidator, schema, localizer[language.split('_')[0]] || localizer.en
    ))
}

export {defineValidator as default};
