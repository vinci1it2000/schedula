import React from 'react';
import Link from 'rc-scroll-anim/lib/ScrollLink';

export default function Point(
    {
        data = [],
        size = '',
        position = '',
        type = '',
        stroke = '',
        isMobile,
        dataSource: {OverPack: {targetId} = {}} = {},
        ...props
    }
) {
    const children = data.map((item, i) => {
        if (item.match('nav') || item.match('footer')) {
            return null;
        }
        const className = `point ${type} ${stroke} ${size}`.trim();
        return (
            <Link
                key={i}
                className={className}
                to={item}
                toHash={false}
                targetId={targetId}
            />
        );
    }).filter((item) => item);
    const wrapperClass = `point-wrapper ${position} ${size}`.trim();
    return (
        <div className={wrapperClass} {...props}>
            <div>
                {children}
            </div>
        </div>
    );
}
