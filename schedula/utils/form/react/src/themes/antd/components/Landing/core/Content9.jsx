import React from 'react';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import QueueAnim from 'rc-queue-anim';
import {getChildrenToRender} from './utils';

class Content9 extends React.PureComponent {
    getBlockChildren = (block, i) => {
        const {isMobile} = this.props;
        const item = block.children;
        const textWrapper = (
            <QueueAnim
                key="text"
                leaveReverse
                delay={isMobile ? [0, 100] : 0}
                {...item.textWrapper}
            >
                <div key="time" {...item.time}>
                    {item.time.children}
                </div>
                <h2 key="title" {...item.title}>
                    <i {...item.icon}>
                        <img src={item.icon.children} alt="img"/>
                    </i>
                    {item.title.children}
                </h2>
                <div key="p" {...item.content}>
                    {item.content.children}
                </div>
            </QueueAnim>
        );
        return (
            <OverPack key={i.toString()} {...block}>
                {isMobile && textWrapper}
                <QueueAnim
                    className="image-wrapper"
                    key="image"
                    type={isMobile ? 'right' : 'bottom'}
                    leaveReverse
                    delay={isMobile ? [100, 0] : 0}
                    {...item.imgWrapper}
                >
                    <div key="image" {...item.img}>
                        <img src={item.img.children} alt="img"/>
                    </div>
                    <div key="name" className="name-wrapper">
                        <div key="name" {...item.name}>
                            {item.name.children}
                        </div>
                        <div key="post" {...item.post}>
                            {item.post.children}
                        </div>
                    </div>
                </QueueAnim>

                {!isMobile && textWrapper}
            </OverPack>
        );
    };

    render() {
        const {...props} = this.props;
        const {dataSource: {OverPack, ...dataSource}} = props;
        delete props.dataSource;
        delete props.isMobile;
        const children = dataSource.block.children.map((d, i) => this.getBlockChildren({...OverPack, ...d}, i));
        return (
            <div {...props} {...dataSource.wrapper}>
                <div {...dataSource.page}>
                    <div {...dataSource.titleWrapper}>
                        {dataSource.titleWrapper.children.map(getChildrenToRender)}
                    </div>
                    <div {...dataSource.block}>{children}</div>
                </div>
            </div>
        );
    }
}

export default Content9;
