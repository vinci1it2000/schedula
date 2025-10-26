import Fields, {generateFields} from "./fields";
import Templates, {generateTemplates} from "./templates";
import Widgets, {generateWidgets} from "./widgets";
import Components, {generateComponents} from "./components";
import notify from './notify'
import {useLocaleStore} from "./models/locale";
export function generateTheme(registerComponents = false) {
    return {
        templates: generateTemplates(),
        widgets: generateWidgets(),
        fields: generateFields(),
        components: generateComponents(registerComponents),
        notify,
        useLocaleStore
    };
}

export {
    Templates,
    Widgets,
    Fields,
    Components,
    generateTemplates,
    generateWidgets,
    generateFields,
    generateComponents
};