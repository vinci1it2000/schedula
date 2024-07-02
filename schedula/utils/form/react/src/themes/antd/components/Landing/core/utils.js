import React from 'react';
import {Button} from 'antd';
import DOMPurify from "dompurify";

export const isImg = /^http(s)?:\/\/([\w-]+\.)+[\w-]+(\/[\w-./?%&=]*)?|^\/\S*$/;

export const getChildrenToRender = (item, i) => {
    let tag = item.name.indexOf('title') === 0 ? 'h1' : 'div';
    tag = item.href ? 'a' : tag;
    let children = typeof item.children === 'string' && item.children.match(isImg)
        ? React.createElement('img', {src: item.children, alt: 'img'})
        : item.children;
    if (item.name.indexOf('button') === 0 && typeof item.children === 'object') {
        children = React.createElement(Button, {
            ...item.children
        });
    } else if (typeof children === 'string') {
        children = HtmlContent(children)
    }
    return React.createElement(tag, {key: i.toString(), ...item}, children);
};

function useSanitizedHtml(htmlString) {
    return DOMPurify.sanitize(htmlString);
}

export function HtmlContent(htmlString) {

    const sanitizedHtml = useSanitizedHtml(htmlString);
    if (typeof htmlString !== 'string') {
        return htmlString;
    }
    return <div dangerouslySetInnerHTML={{__html: sanitizedHtml}}/>;
}