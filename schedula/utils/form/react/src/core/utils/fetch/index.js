import {gzip, ungzip} from 'pako';

export default async function post(
    {
        url,
        data = {},
        form,
        headers,
        method = 'POST',
        rawResponse = false,
        ...props
    }) {
    let init = {
        method,
        crossDomain: true,
        cache: 'no-cache',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': form.state.csrf_token,
            'Content-Encoding': 'gzip',
            'Accept-Encoding': 'gzip',
            'Accept-Language': form.state.language,
            ...headers
        },
        redirect: 'follow',
        referrerPolicy: 'unsafe-url',
    }
    if (method !== 'GET') {
        init.body = gzip(JSON.stringify(data))
    }
    if (window.getPublicPath && url.startsWith('/')) {
        let publicPath = window.getPublicPath()
        if (publicPath.endsWith('/'))
            url = url.slice(1)
        url = `${publicPath}${url}`;
    }
    return fetch(url, {...init, ...props}).then(async (response) => {
        let debugUrl, messages;
        if (response.headers.has('Debug-Location')) {
            debugUrl = response.headers.get('Debug-Location')
        }
        if (response.headers.has('N-CSRF-Token')) {
            const csrf_token = response.headers.get('N-CSRF-Token')
            form.setState((state) => ({...state, csrf_token}))
        }
        if (response.redirected) {
            window.location.href = response.url;
        }
        if (response.headers.has('X-Flash-Messages')) {
            messages = response.headers.get('X-Flash-Messages')
            if (response.headers.get('X-Flash-Messages-Encoding').includes('gzip')) {
                messages = ungzip(Uint8Array.from(atob(messages), c => c.charCodeAt(0)), {to: 'string'})
            }
            messages = JSON.parse(messages)
        }
        const isJson = (response.headers.get('content-type') || '').includes('application/json');
        if (response.status !== 200) {
            let errors = {error: response.statusText}
            if (isJson) {
                errors = {...errors, ...((await response.json() || {}).response || {})};
            }
            return {data: errors, response, messages}
        }
        return {
            data: rawResponse ? response : (isJson ? await response.json() : await response.text()),
            debugUrl,
            messages
        }
    })
}
