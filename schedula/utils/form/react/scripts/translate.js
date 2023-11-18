import fs from 'fs';
import merge  from "lodash/merge";

let key = process.argv[2], module
if (fs.existsSync(`./src/themes/antd/models/locale/${key}.mjs`)) {
    module = import(`../src/themes/antd/models/locale/${key}.mjs`).then(module => {
        let {default: d, ...locale} = module.default
        return merge({}, d, locale)
    })
} else {
    module = import(`antd/locale/${key}`).then(module => module.default.default).catch(() => {
    });
}
module.then((locale) => {
    var jsonData = JSON.stringify(Object.assign({}, locale, {language: key}));
    console.log(jsonData);
})
