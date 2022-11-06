import React from 'react';
import MuiMarkdown from 'mui-markdown'
import nunjucks from 'nunjucks';

var env = new nunjucks.Environment();
env.addFilter('decimal', function (val, i, lang) {
    let n = i ? Math.pow(10, i) : 1;
    return (Math.round((val + Number.EPSILON) * n) / n).toLocaleString(lang || 'it');
});
env.addFilter('locale', function (val, lang) {
    return (val).toLocaleString(lang || 'it');
});


function format2(string, args = [], kwargs = {}) {
    let i = -1;
    return string.replace(/{(\d+)}/g, function (match, number) {
        return typeof args[number] != 'undefined' ? args[number] : match;
    }).replace(/{(\w[^}]*)}/g, function (match, key) {
        return typeof kwargs[key] != 'undefined' ? kwargs[key] : match;
    }).replace(/{(\s*)}/g, function (match) {
        i++;
        return typeof args[i] != 'undefined' ? args[i] : match;
    });
};

export default function _markdown(props) {
    let args = [], kwargs = {}, data = props.context.props.formData || {}, md;
    if (typeof data !== 'object') {
        args = [data]
    } else if (Array.isArray(data)) {
        args = data
    } else {
        kwargs = data
    }
    md = format2(env.renderString(props.children.join('\n'), {
        data,
        props,
        window
    }), args, kwargs);
    return (<MuiMarkdown>
        {md}
    </MuiMarkdown>);
}