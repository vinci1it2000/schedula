export default function getTheme(theme = 'antd') {
    return new Promise((resolve, reject) => {
        if (typeof theme === 'string') {
            import((`./${theme}`)).then(({generateTheme}) => {
                resolve(generateTheme(true))
            }).catch(err => {
                reject(err)
            });
        } else {
            resolve(theme)
        }
    })
}