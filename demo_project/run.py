"""
运行 Demo 项目爬虫
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.crawler import CrawlerProcess
from src.settings.settings_manager import SettingsManager
from demo_project.spiders.simple_spider import SimpleSpider
from demo_project.spiders.quotes_spider import QuotesSpider


async def run_simple_spider():
    """运行简单爬虫"""
    print("\n" + "="*70)
    print("🚀 启动简单测试爬虫")
    print("="*70 + "\n")
    
    settings = SettingsManager({
        'PROJECT_NAME': 'simple_demo',
        'CONCURRENT_REQUESTS': 2,
        'LOG_LEVEL': 'INFO',
    })
    
    process = CrawlerProcess(settings)
    await process.crawl(SimpleSpider)
    await process.start()
    
    print("\n" + "="*70)
    print("✅ 简单爬虫运行完成")
    print("="*70 + "\n")


async def run_quotes_spider():
    """运行引用爬虫"""
    print("\n" + "="*70)
    print("🚀 启动 Quotes 爬虫（演示完整功能）")
    print("="*70 + "\n")
    
    settings = SettingsManager({
        'PROJECT_NAME': 'quotes_demo',
        'CONCURRENT_REQUESTS': 3,
        'LOG_LEVEL': 'INFO',
    })
    
    process = CrawlerProcess(settings)
    await process.crawl(QuotesSpider)
    await process.start()
    
    print("\n" + "="*70)
    print("✅ Quotes 爬虫运行完成")
    print("="*70 + "\n")


async def main():
    """主函数"""
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#" + " "*20 + "Cola 框架测试演示" + " "*28 + "#")
    print("#" + " "*68 + "#")
    print("#"*70 + "\n")
    
    # 选择要运行的爬虫
    print("请选择要运行的爬虫:")
    print("1. 简单爬虫 (httpbin.org 测试)")
    print("2. Quotes 爬虫 (quotes.toscrape.com)")
    print("3. 运行所有爬虫")
    
    choice = input("\n请输入选项 (1/2/3) [默认: 1]: ").strip() or "1"
    
    if choice == "1":
        await run_simple_spider()
    elif choice == "2":
        await run_quotes_spider()
    elif choice == "3":
        await run_simple_spider()
        await run_quotes_spider()
    else:
        print("❌ 无效选项，运行简单爬虫")
        await run_simple_spider()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断爬虫")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
